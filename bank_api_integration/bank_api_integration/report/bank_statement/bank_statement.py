# Copyright (c) 2013, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe

def execute(filters=None):
	columns, data = [], []
	columns = [{'label': 'Txn Date', 'fieldname': 'txn_date', 'fieldtype': 'Data', 'options': None, 'width': 180},
	{'label': 'Credit', 'fieldname': 'credit', 'fieldtype': 'Currency', 'options': 'Currency', 'width': 180},
	{'label': 'Debit', 'fieldname': 'debit', 'fieldtype': 'Currency', 'options': 'Currency', 'width': 180},
	{'label': 'Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'options': 'Currency', 'width': 180},
	{'label': 'Remarks', 'fieldname': 'remarks', 'fieldtype': 'Data', 'options': None, 'width': 180}]
	return columns, data
