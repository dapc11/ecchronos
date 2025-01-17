#
# Copyright 2019 Telefonaktiebolaget LM Ericsson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import time
import re
from subprocess import Popen, PIPE
from behave import when, then  # pylint: disable=no-name-in-module
from ecc_step_library.common_steps import match_and_remove_row, strip_and_collapse, validate_header, validate_last_table_row  # pylint: disable=line-too-long


TABLE_ROW_FORMAT_PATTERN = r'\| .* \| {0} \| {1} \| (COMPLETED|IN_QUEUE|WARNING|ERROR) \| \d+[.]\d+ \| .* \| .* \|'
ID_PATTERN = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
SUMMARY_PATTERN = r'Summary: \d+ completed, \d+ in queue, \d+ warning, \d+ error'

TABLE_HEADER = r'| Id | Keyspace | Table | Status | Repaired(%) | Completed at | Next repair | Recurring |'


def run_ecc_repair_status(context, params):
    cmd = [context.config.userdata.get("ecctool")] + ["repair-status"] + params
    context.proc = Popen(cmd, stdout=PIPE, stderr=PIPE) # pylint: disable=consider-using-with
    (context.out, context.err) = context.proc.communicate()


def table_row(keyspace, table):
    return TABLE_ROW_FORMAT_PATTERN.format(keyspace, table)


def token_row():
    return "\\| [-]?\\d+ \\| [-]?\\d+ \\| .* \\| .* \\| (True|False) \\|"


@when(u'we list all tables')
def step_list_tables(context):
    run_ecc_repair_status(context, [])

    output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')
    context.header = output_data[0:3]
    context.rows = output_data[3:-1]
    context.summary = output_data[-1:]


@when(u'we list all tables with a limit of {limit}')
def step_list_tables_with_limit(context, limit):
    run_ecc_repair_status(context, ['--limit', limit])

    output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')
    context.header = output_data[0:3]
    context.rows = output_data[3:-1]
    context.summary = output_data[-1:]


@when(u'we list all tables for keyspace {keyspace} with a limit of {limit}')
def step_list_tables_for_keyspace_with_limit(context, keyspace, limit):
    run_ecc_repair_status(context, ['--keyspace', keyspace, '--limit', limit])

    output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')
    context.header = output_data[0:3]
    context.rows = output_data[3:-1]
    context.summary = output_data[-1:]


@when(u'we list all tables for keyspace {keyspace}')
def step_list_tables_for_keyspace(context, keyspace):
    run_ecc_repair_status(context, ['--keyspace', keyspace])

    output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')
    context.header = output_data[0:3]
    context.rows = output_data[3:-1]
    context.summary = output_data[-1:]


@when(u'we show job {keyspace}.{table} with a limit of {limit}')
def step_show_table_with_limit(context, keyspace, table, limit):
    run_ecc_repair_status(context, ['--keyspace', keyspace, '--table', table])

    job_id = re.search(ID_PATTERN, context.out.decode('ascii')).group(0)
    assert job_id
    run_ecc_repair_status(context, ['--id', job_id, '--limit', limit])
    output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')

    context.table_info = output_data[0:7]
    context.header = output_data[8:9]
    context.rows = output_data[11:]


@when(u'we list jobs for table {keyspace}.{table}')
def step_show_table(context, keyspace, table):
    run_ecc_repair_status(context, ['--keyspace', keyspace, '--table', table])

    output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')
    context.header = output_data[0:3]
    context.rows = output_data[3:-1]
    context.summary = output_data[-1:]


@then(u'the output should contain a valid header')
def step_validate_list_tables_header(context):
    validate_header(context.header, TABLE_HEADER)


@then(u'the output should contain a row for {keyspace}.{table}')
def step_validate_list_tables_row(context, keyspace, table):
    expected_row = table_row(keyspace, table)
    match_and_remove_row(context.rows, expected_row)


@then(u'the output should not contain more rows')
def step_validate_list_rows_clear(context):
    validate_last_table_row(context.rows)


@then(u'the output should contain {limit:d} row')
def step_validate_list_tables_contains_rows_with_limit(context, limit):
    rows = context.rows

    assert len(rows) == limit + 1, "Expecting only {0} table element from {1}".format(limit, rows)

    for _ in range(limit):
        step_validate_list_tables_row(context, ".*", ".*")

    step_validate_list_rows_clear(context)


@then(u'the output should contain summary')
def step_validate_list_tables_contains_rows(context):
    assert len(context.summary) == 1, "Expecting only 1 row summary"

    summary = context.summary[0]
    assert re.match(SUMMARY_PATTERN, summary), "Faulty summary '{0}'".format(summary)


@then(u'the expected header should be for {keyspace}.{table}')
def step_validate_expected_show_table_header(context, keyspace, table):
    table_info = context.table_info
    assert re.match("Id : .*", strip_and_collapse(table_info[0])), "Faulty Id '{0}'".format(table_info[0])
    assert strip_and_collapse(
        table_info[1]) == "Keyspace : {0}".format(keyspace), "Faulty keyspace '{0}'".format(table_info[1])
    assert strip_and_collapse(
        table_info[2]) == "Table : {0}".format(table), "Faulty table '{0}'".format(table_info[2])
    assert re.match("Status : (COMPLETED|IN_QUEUE|WARNING|ERROR)", strip_and_collapse(table_info[3])),\
        "Faulty status '{0}'".format(table_info[3])
    assert re.match("Repaired\\(%\\) : \\d+[.]\\d+", strip_and_collapse(table_info[4])),\
        "Faulty repaired(%) '{0}'".format(table_info[4])
    assert re.match(
        "Completed at : .*", strip_and_collapse(table_info[5])), "Faulty repaired at '{0}'".format(table_info[5])
    assert re.match(
        "Next repair : .*", strip_and_collapse(table_info[6])), "Faulty next repair '{0}'".format(table_info[6])


def remove_token_row(context):
    expected_row = token_row()

    found_row = -1

    for idx, row in enumerate(context.rows):
        row = strip_and_collapse(row)
        if re.match(expected_row, row):
            found_row = int(idx)
            break

    assert found_row != -1, "{0} not found in {1}".format(expected_row, context.rows)
    del context.rows[found_row]


@then(u'the token list should contain {limit:d} rows')
def step_validate_token_list(context, limit):
    for _ in range(limit):
        remove_token_row(context)

    step_validate_list_rows_clear(context)


@then('the job for {keyspace}.{table} disappears when it is finished')
def verify_job_disappeared(context, keyspace, table):  # pylint: disable=unused-argument
    job_id = re.search(ID_PATTERN, context.response.text).group(0)
    assert job_id
    timeout = time.time() + 150
    output_data = []
    while "Repair job not found" not in output_data:
        run_ecc_repair_status(context, ['--id', job_id, '--limit', "1"])
        output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')
        time.sleep(1)
        assert time.time() < timeout


@then('the job for {keyspace}.{table} change status to completed')
def verify_job_status_changed(context, keyspace, table):  # pylint: disable=unused-argument
    job_id = re.search(ID_PATTERN, context.response.text).group(0)
    assert job_id
    timeout = time.time() + 150
    output_data = []
    while "Status         : COMPLETED" not in output_data:
        run_ecc_repair_status(context, ['--id', job_id, '--limit', "1"])
        output_data = context.out.decode('ascii').lstrip().rstrip().split('\n')
        time.sleep(1)
        assert time.time() < timeout
