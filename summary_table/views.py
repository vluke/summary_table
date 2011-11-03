# -*- coding: utf-8 -*-

import csv

from django.db.models import Q
from django.http import HttpResponse
from django.template import Context
from django.shortcuts import render_to_response, redirect
from django.views.decorators.cache import never_cache

from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.creativecommonshandler import CreativeCommonsHandler
from tardis.tardis_portal.models import Experiment, DatafileParameter, ParameterName, Dataset_File
from tardis.tardis_portal.shortcuts import render_response_index

import json

import logging
logger = logging.getLogger(__name__)


@never_cache
@authz.experiment_access_required
def index(request, experiment_id):
    url = 'summary_table/index.html'
    context = _context(experiment_id)
    context['show_popout_link'] = True
    return HttpResponse(render_response_index(request, url, context))

def _context(experiment_id):
    c = Context()
    experiment = Experiment.objects.get(pk=experiment_id)

    parameter_names = ParameterName.objects.filter(datafileparameter__parameterset__dataset_file__dataset__experiment=experiment).distinct()
    datafiles = Dataset_File.objects.filter(dataset__experiment=experiment)

    descs = [{'mDataProp': 'filename', 'sTitle': 'filename'}]
    for x in parameter_names:
        descs.append({'mDataProp': str(x.id), 'sTitle': x.name})
    c['joined'] = json.dumps(descs)
    c['experiment'] = experiment
    return c


@authz.experiment_access_required
def full_page(request, experiment_id):
    url = 'summary_table/full_page.html'
    context = _context(experiment_id)
    return HttpResponse(render_response_index(request, url, context))


@authz.experiment_access_required
def table(request, experiment_id):
    # http://datatables.net/usage/server-side
    logger.debug(request.GET)
    if int(request.GET['iSortingCols']) != 1:
        raise Exception('this should not happen')
    sort_col_index = request.GET['iSortCol_0']
    sort_col_name = request.GET['mDataProp_' + sort_col_index]
    sort_desc = request.GET['sSortDir_0'] == 'desc'

    experiment = Experiment.objects.get(pk=experiment_id)

    parameter_names = ParameterName.objects.filter(datafileparameter__parameterset__dataset_file__dataset__experiment=experiment).distinct()
    datafiles = Dataset_File.objects.filter(dataset__experiment=experiment)

    if sort_col_name == 'filename':
        if sort_desc:
            datafiles = datafiles.order_by('-filename')
        else:
            datafiles = datafiles.order_by('filename')
        post_filter = False
    else:
        datafiles = datafiles.order_by('filename')
        post_filter = True

    filter = request.GET['sSearch']
    filtered_datafiles = _filter(datafiles, filter)

    limit = int(request.GET['iDisplayLength'])
    offset = int(request.GET['iDisplayStart'])
    dfs = [(x.id, x.filename) for x in filtered_datafiles[offset:offset+limit]]
    df_ids = [x[0] for x in dfs]

    params_by_file = _params_by_file(df_ids, parameter_names)

    rows = _get_rows(dfs, parameter_names, params_by_file, sort_desc, post_filter, sort_col_name)

    resp = {}
    resp['sEcho'] = int(request.GET['sEcho'])
    resp['aaData'] = rows
    resp['iTotalRecords'] = datafiles.count()
    resp['iTotalDisplayRecords'] = filtered_datafiles.count()
    return HttpResponse(json.dumps(resp), mimetype='application/json')


def _get_rows(dfs, parameter_names, params_by_file, sort_desc, post_filter, sort_col_name):
    pndict = dict([[pn.id, pn] for pn in parameter_names])
    pn_ids = [x for x in pndict.keys()]
    rows = []
    for dft in dfs:
        df_id = dft[0]
        df_name = dft[1]

        row = {}
        row['filename'] = df_name
        for pn_id in pn_ids:
            row[str(pn_id)] = ''
            if post_filter:
                row['sortable'] = 0
        for pn_id, params in params_by_file[df_id].items():
            pn = pndict[pn_id]
            if pn.isString() or pn.isLongString():
                row[str(pn_id)] = ','.join([param['string_value'] for param in params])
            elif pn.isNumeric():
                row[str(pn_id)] = ','.join([str(param['numerical_value']) for param in params])
            elif pn.isDateTime():
                row[str(pn_id)] = ','.join([str(param['datetime_value']) for param in params])

            if post_filter and sort_col_name == str(pn.id):
                if len(params) > 0:
                    if pn.isString() or pn.isLongString():
                        row['sortable'] = sorted([x['string_value'] for x in params])[0]
                    elif pn.isNumeric():
                        row['sortable'] = sorted([x['numerical_value'] for x in params])[0]
                    elif pn.isDateTime():
                        row['sortable'] = sorted([x['datetime_value'] for x in params])[0]
                    else:
                        row['sortable'] = 0
        rows.append(row)

    if post_filter:
        rows = sorted(rows, key=lambda x: x['sortable'], reverse=sort_desc)
        for row in rows:
            del row['sortable']
    return rows


def _params_by_file(df_ids, parameter_names):
    name_ids = [pn.id for pn in parameter_names]
    params_by_file = {}
    dfps = DatafileParameter.objects.filter(parameterset__dataset_file__in=df_ids, name__in=name_ids).values('parameterset__dataset_file__id', 'name__id', 'numerical_value', 'datetime_value', 'string_value')

    for df_id in df_ids:
        params_by_file[df_id] = {}
    for dfp in dfps:
        df_id = dfp['parameterset__dataset_file__id']
        n_id = dfp['name__id']

        dfps_by_name = params_by_file[df_id]

        if n_id not in dfps_by_name:
            dfps_by_name[n_id] = []

        dfp_vals = {'datetime_value': dfp['datetime_value'], 'numerical_value': dfp['numerical_value'], 'string_value': dfp['string_value'] }
        dfps_by_name[n_id].append(dfp)
    return params_by_file


def _filter(datafile_queryset, filter):
    if len(filter) < 1:
        return datafile_queryset
    else:
        query = Q(filename__icontains=filter)
        query |= Q(datafileparameterset__datafileparameter__string_value__icontains=filter)
        query |= Q(datafileparameterset__datafileparameter__numerical_value__icontains=filter)
        return datafile_queryset.filter(query).distinct()

@authz.experiment_access_required
def csv_export(request, experiment_id):
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename="exported_%s.csv"' % experiment_id

    parameter_names = list(ParameterName.objects.filter(datafileparameter__parameterset__dataset_file__dataset__experiment=experiment_id).distinct())
    datafiles = list(Dataset_File.objects.filter(dataset__experiment=experiment_id))
    datafile_ids = [df.id for df in datafiles]

    params_by_file = _params_by_file(datafile_ids, parameter_names)

    writer = csv.writer(response)
    header_row = ['filename'] + [pn.name for pn in parameter_names]
    writer.writerow(header_row)
    for datafile in datafiles:
        row = []
        params = params_by_file[datafile.id]

        row.append(datafile.filename)
        for parameter_name in parameter_names:
            if parameter_name.id in params:
                specific_params = params[parameter_name.id]
                if parameter_name.isString() or pn.isLongString():
                    vals = [str(param['string_value']) for param in specific_params]
                elif parameter_name.isNumeric():
                    vals = [str(param['numerical_value']) for param in specific_params]
                elif parameter_name.isDateTime():
                    vals = [str(param['datetime_value']) for param in specific_params]
                else:
                    vals = []
                row.append(','.join(vals))
            else:
                row.append('')

        writer.writerow(row)

    return response
