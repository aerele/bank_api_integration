# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import banking_api
from banking_api.common_provider import CommonProvider
from frappe import _
from frappe.utils import getdate

class BankAPIIntegrationSettings(Document):
	pass

provider  = frappe.db.get_single_value('Bank API Integration Settings', 'bank_api_provider')
if not provider:
	provider = 'Test'
prov = CommonProvider(provider)

@frappe.whitelist()
def fetch_balance():
	return prov.fetch_balance()

@frappe.whitelist()
def sync_transactions():
	try:
		transactions = prov.fetch_statement()

		result = []
		for transaction in reversed(transactions):
			result += new_bank_transaction(transaction)

		if result:
			frappe.logger().info("Bank API added {} new Bank Transactions".format(
				len(result)))
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("Banking API transactions sync error"))


def new_bank_transaction(transaction):
	result = []
	bank_account = frappe.db.get_value("Bank Account", dict(bank_account_no=transaction["account_no"]))
	if not frappe.db.exists("Bank Transaction", dict(transaction_id=transaction["txn_id"])):
		new_transaction = frappe.get_doc({
			'doctype': 'Bank Transaction',
			'date': getdate(transaction['txn_date'].split(' ')[0]),
			"transaction_id": transaction["txn_id"],
			'debit': abs(float(transaction['debit'].replace(',',''))) if transaction['debit'] else 0,
			'credit': abs(float(transaction['credit'].replace(',',''))) if transaction['credit'] else 0,
			'description': transaction['remarks'],
			'bank_account': bank_account
		})
		new_transaction.save()
		new_transaction.submit()
		result.append(new_transaction.name)
	return result