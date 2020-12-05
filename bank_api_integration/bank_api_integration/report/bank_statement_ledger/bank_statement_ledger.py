# Copyright (c) 2013, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns, data = [], []
	columns = [{'label': 'Date', 'fieldname': 'date', 'fieldtype': 'Data', 'options': None, 'width': 180},
	{'label': 'Transaction ID', 'fieldname': 'transaction_id', 'fieldtype': 'Data', 'options': None, 'width': 180},
	{'label': 'Credit', 'fieldname': 'credit', 'fieldtype': 'Currency', 'options': 'Currency', 'width': 180},
	{'label': 'Debit', 'fieldname': 'debit', 'fieldtype': 'Currency', 'options': 'Currency', 'width': 180},
	{'label': 'Description', 'fieldname': 'description', 'fieldtype': 'Data', 'options': None, 'width': 180}]
	data = frappe.get_list("Bank Transaction", fields=["date", "transaction_id", "credit", "debit", "description"])
	return columns, data
