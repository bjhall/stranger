import logging
import coloredlogs
import click
import gzip

from pprint import pprint as pp
from codecs import (open, getreader)

from stranger.resources import repeats_json_path
from stranger.utils import (parse_repeat_file, get_repeat_info, get_info_dict, get_variant_line)
from stranger.vcf_utils import print_headers
from stranger.__version__ import __version__

LOG = logging.getLogger(__name__)
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()

@click.command()
@click.argument('vcf')
@click.option('-f', '--repeats-file',
    type = click.Path(exists=True),
    help="Path to a file with repeat definitions. See README for explanation",
    default=repeats_json_path,
    show_default=True,
)
@click.option('--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True)
@click.option('--loglevel', default='INFO', type=click.Choice(LOG_LEVELS),
              help="Set the level of log output.", show_default=True)
@click.pass_context
def cli(context, vcf, repeats_file, loglevel):
    """Annotate str variants with str status"""
    coloredlogs.install(level=loglevel)
    LOG.info("Running stranger version %s", __version__)

    repeat_information = None
    repeats_file_type = 'tsv'
    if repeats_file.endswith('.json'):
        repeats_file_type = 'json'
    LOG.info("Parsing repeats file %s", repeats_file)

    with open(repeats_file, 'r') as file_handle:
        repeat_information = parse_repeat_file(file_handle, repeats_file_type)

    if not repeat_information:
        LOG.warning("Could not find any repeat info")
        context.abort()

    header_definitions = [
        {
            'id': 'STR_STATUS', 'num': 'A', 'type': 'String',
            'desc': 'Repeat expansion status. Alternatives in [normal, pre_mutation, full_mutation]'
        },
        {
            'id': 'STR_NORMAL_MAX', 'num': '1', 'type': 'Integer',
            'desc': 'Max number of repeats allowed to call as normal'
        },
        {
            'id': 'STR_FULLMUT_MIN', 'num': '1', 'type': 'Integer',
            'desc': 'Min number of repeats required to call as full mutation'
        }
    ]

    stranger_headers = []
    for hdef in header_definitions:
        header = '##INFO=<ID={0},Number={1},Type={2},Description="{3}">'.format(
            hdef.get('id'), hdef.get('num'), hdef.get('type'), hdef.get('desc'))
        stranger_headers.append(header)
            

    if vcf.endswith('.gz'):
        LOG.info("Vcf is zipped")
        vcf_handle = getreader('utf-8')(gzip.open(vcf), errors='replace')
    else:
        vcf_handle = open(vcf, mode='r', encoding='utf-8', errors='replace')

    LOG.info("Parsing variants from %s", vcf)
    for line in vcf_handle:
        line = line.rstrip()
        if line.startswith('#'):
            if line.startswith('##'):
                click.echo(line)
                continue
            # Print the new header lines describing stranger annotation
            for header in stranger_headers:
                click.echo(header)
            # Print the vcf header line
            header_info = line[1:].split('\t')
            click.echo(line)
            continue
        variant_info = dict(zip(header_info, line.split('\t')))
        variant_info['alts'] = variant_info['ALT'].split(',')
        variant_info['info_dict'] = get_info_dict(variant_info['INFO'])
        repeat_data = get_repeat_info(variant_info, repeat_information)
        if repeat_data:
            variant_info['info_dict']['STR_STATUS'] = repeat_data['repeat_strings']
            variant_info['info_dict']['STR_NORMAL_MAX'] = str(repeat_data['lower'])
            variant_info['info_dict']['STR_FULLMUT_MIN'] = str(repeat_data['upper'])

        click.echo(get_variant_line(variant_info, header_info))
