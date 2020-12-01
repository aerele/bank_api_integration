# Copyright (c) 2013, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns, data = [], []
	columns = [{'label': 'Date', 'fieldname': 'date', 'fieldtype': 'Data', 'options': None, 'width': 180},
	{'label': 'Account No', 'fieldname': 'account_no', 'fieldtype': 'Data', 'options': None, 'width': 180},
	{'label': 'Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'options': 'Currency', 'width': 180},
	{'label': 'Currency', 'fieldname': 'currency', 'fieldtype': 'Data', 'options': None, 'width': 180}]
	data = frappe.get_list("Bank Balance", fields=["date", "account_no", "balance", "currency"])
	return columns, data