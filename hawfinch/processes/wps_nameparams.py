from pywps import Process
from pywps import ComplexOutput, Format
from pywps import LiteralInput, LiteralOutput, BoundingBoxInput
from pywps.exceptions import InvalidParameterValue
from pywps.app.Common import Metadata

from hawfinch.run_name import run_name
from datetime import timedelta

import logging
LOGGER = logging.getLogger('PYWPS')


class RunNAME(Process):
    """
    Notes
    -----

    This will take and regurgitate all the parameters required to run NAME.
    It should make it easier to then add in the actual process.
    """
    def __init__(self):
        inputs = [
            LiteralInput('title', 'Title', data_type='string',
                         abstract='Title of run'),
            LiteralInput('longitude', 'Longitude', data_type='float',
                         abstract='Location of release',
                         default=-24.867222),
            LiteralInput('latitude', 'Latitude', data_type='float',
                         abstract='Location of release',
                         default=16.863611),
            LiteralInput('elevation', 'Elevation', data_type='integer',
                         abstract='Elevation of release, m agl for land, m asl for marine release',
                         default=10, min_occurs=0),
            # LiteralInput('elevation_range_min','Elevation Range Min', data_type='integer',
            #              abstract='Minimum range of elevation',
            #              default=None, min_occurs=0),
            # LiteralInput('elevation_range_max', 'Elevation Range Max', data_type='integer',
            #              abstract = 'Maximum range of elevation',
            #              default=None, min_occurs=0),

            LiteralInput('runBackwards', 'Run Backwards', data_type='boolean',
                         abstract = 'Whether to run backwards in time or forwards',
                         default = '1', min_occurs=0),
            LiteralInput('time', 'Time to run model over', data_type='integer',
                         abstract = '',
                         default=1),
            LiteralInput('timeFmt',' ', data_type='string',
                         abstract='number of days/hours NAME will run over. Maximum is 20 days.',
                         allowed_values = ['days','hours'], default='days'),
            # Use fake bbox input until BoundingBoxInput supported by pywps
            # BoundingBoxInput('domain', 'Computational Domain', crss=['epsg:4326'],
            #                  abstract='Coordinates to run NAME within',
            #                  min_occurs=1),
            LiteralInput('minX',
                         'Minimum longitude',
                         abstract='Minimum longitude.',
                         data_type='float',
                         default=-180,
                         min_occurs=1),
            LiteralInput('maxX',
                         'Maximum longitude',
                         abstract='Maximum longitude.',
                         data_type='float',
                         default=180,
                         min_occurs=1),
            LiteralInput('minY',
                         'Minimum latitude',
                         abstract='Minimum latitude.',
                         data_type='float',
                         default=-90,
                         min_occurs=1),
            LiteralInput('maxY',
                         'Maximum latitude',
                         abstract='Maximum latitude.',
                         data_type='float',
                         default=90,
                         min_occurs=1),
            LiteralInput('elevationOut', 'Output elevation averaging range(s)', data_type='string',
                         abstract='Elevation range where the particle number is counted (m agl)'
                                  ' Example: 0-100',
                         default='0-100', min_occurs=1, max_occurs=4),
            LiteralInput('resolution','Resolution', data_type='float',
                         abstract='degrees, note the UM global Met data was only 17Km resolution',
                         allowed_values=[0.05,0.25], default=0.25, min_occurs=0),
            LiteralInput('timestamp','Run Type', data_type='string',
                         abstract='how often NAME will run',
                         allowed_values=['3-hourly','daily']),
            LiteralInput('dailytime','Daily run time (UTC)', data_type='time',
                         abstract='if running daily, at what time will it run',
                         min_occurs = 0),
            LiteralInput('dailyreleaselen', 'Daily release length', data_type='integer',
                         abstract='if running daily, over how many hours will it release?',
                         allowed_values=[1, 3, 6, 12, 24], min_occurs=0),
            LiteralInput('startdate', 'Start date', data_type='date',
                         abstract='UTC start date of runs'),
            LiteralInput('enddate', 'End date', data_type='date',
                         abstract = 'UTC end date of runs (inclusive)'),
            ]
        outputs = [
            LiteralOutput('runid', 'Run ID', data_type='string',
                          abstract='Unique run identifier, this is needed to create plots'),
            ComplexOutput('FileContents', 'Output files (zipped)',
                          abstract='Output files (zipped)',
                          supported_formats=[Format('application/x-zipped-shp')],
                          as_reference=True),
            ComplexOutput('SummaryPlot', 'Summary Plot',
                          abstract='Summary plot of whole time period',
                          supported_formats=[Format('image/tiff')],
                          as_reference=True),
            ]

        super(RunNAME, self).__init__(
            self._handler,
            identifier='runname',
            title='Run NAME-on-JASMIN',
            abstract='Run NAME using user-defined settings',
            version='0.1',
            metadata=[
                Metadata('NAME-on-JASMIN guide', 'http://jasmin.ac.uk/jasmin-users/stories/processing/'),
            ],
            inputs=inputs,
            outputs=outputs,
            store_supported=True,
            status_supported=True)

    def _handler(self, request, response):

        # Need to process the elevationOut inputs from a list of strings, into an array of tuples.
        ranges = []
        for elevationrange in request.inputs['elevationOut']:
            if '-' in elevationrange.data:
                minrange, maxrange = elevationrange.data.split('-')
                ranges.append((int(minrange), int(maxrange))) # need to error catch int() and min < max
            else:
                raise InvalidParameterValue(
                    'The value "{}" does not contain a "-" character to define a range, '
                    'e.g. 0-100'.format(elevationrange.data))

        domains = []

        if request.inputs['minX'][0].data < -180:
            raise InvalidParameterValue('Bounding box minimum longitude input cannot be below -180')
        if request.inputs['maxX'][0].data > 180:
            raise InvalidParameterValue('Bounding box maximum longitude input cannot be above 180')
        if request.inputs['minY'][0].data < -90:
            raise InvalidParameterValue('Bounding box minimum latitude input cannot be below -90')
        if request.inputs['maxY'][0].data > 90:
            raise InvalidParameterValue('Bounding box minimum latitude input cannot be above 90')
        
        #minY, minX, maxY, maxX
        domains.append(request.inputs['minY'][0].data)
        domains.append(request.inputs['minX'][0].data)
        domains.append(request.inputs['maxY'][0].data)
        domains.append(request.inputs['maxX'][0].data)

        # If minX and maxX are 180, need to reset to 179.9
        if domains[1] == -180 and domains[3] == 180:
            domains[1] = -179.875
            domains[3] = 179.9

        params = dict()
        for p in request.inputs:
            if p == 'elevationOut':
                params[p] = ranges
            elif p == 'domain':
                params[p] = domains
            else:
                params[p] = request.inputs[p][0].data

        # Need to test start and end dates make sense relative to each other
        if params['startdate'] >= params['enddate'] + timedelta(days=1):
            raise InvalidParameterValue('The end date is earlier than the start date!')

        if (params['enddate'] + timedelta(days=1)) - params['startdate'] >= timedelta(days=93):
            raise InvalidParameterValue('Can only run across a maximum of three months in one go')

        # Need to test we don't run too far backwards/forwards
        if params['timeFmt'] == 'days':
            if params['time'] > 20:
                raise InvalidParameterValue('Can only run NAME over a maximum of 20 days forwards/backwards')
        else:
            if params['time'] > 20 * 24:
                raise InvalidParameterValue('Can only run NAME over a maximum of 20 days forwards/backwards')

        response.update_status('Processed parameters', 5)

        outdir, zippedfile, mapfile = run_name(params, response)

        response.outputs['FileContents'].file = zippedfile + '.zip'
        response.outputs['runid'].data = outdir
        response.outputs['SummaryPlot'].file = mapfile

        response.update_status('done', 100)
        return response
