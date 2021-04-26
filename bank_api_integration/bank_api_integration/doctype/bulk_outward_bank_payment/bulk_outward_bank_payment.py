# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, comma_and
from frappe.model.mapper import get_mapped_doc

class BulkOutwardBankPayment(Document):
	def validate(self):
		total_payment_amount = 0
		for row in self.outward_bank_payment_details:
			total_payment_amount+=flt(row.amount)
		self.total_payment_amount = total_payment_amount
		self.no_of_payments = len(self.outward_bank_payment_details)

	def create_outward_bank_payments(self):
		if self.status == 'Approved':
			failed_obp_list = []
			for row in self.outward_bank_payment_details:
				data = {'doctype': 'Outward Bank Payment',
				'party_type': row.party_type,
				'party': row.party,
				'amount': row.amount,
				'transaction_type': self.transaction_type,
				'company_bank_account': self.company_bank_account,
				'reconcile_action': self.reconcile_action,
				'bobp': self.name}
				if not frappe.db.exists('Outward Bank Payment', data):
					doc = frappe.get_doc({'doctype': 'Outward Bank Payment',
					'party_type': row.party_type,
					'party': row.party,
					'amount': row.amount,
					'transaction_type': self.transaction_type,
					'company_bank_account': self.company_bank_account,
					'reconcile_action': self.reconcile_action,
					'bobp': self.name})
					doc.save()
					doc.submit()
					status = frappe.db.get_value('Outward Bank Payment', doc.name, 'status')
					if status in  ['Initiation Error', 'Initiation Failed']:
						failed_obp_list.append(comma_and("""<a href="#Form/Outward Bank Payment/{0}">{1}</a>""".format(doc.name, doc.name)))
					frappe.db.set_value('Outward Bank Payment Details',{'parent':self.name,
						'party_type': row.party_type,
						'party': row.party,
						'amount': row.amount},'outward_bank_payment',doc.name)
					frappe.db.set_value('Outward Bank Payment Details',{'parent':self.name,
						'party_type': row.party_type,
						'party': row.party,
						'amount': row.amount,
						'outward_bank_payment':doc.name},'status', status)
			frappe.db.commit()
			self.reload()
			if failed_obp_list:
				failed_obp = ','.join(failed_obp_list)
				frappe.throw(_(f"Initiation failed for the below obp(s) {failed_obp}"))
			else:
				frappe.msgprint(_('Payment initiated successfully'))



@frappe.whitelist()
def fetch_failed_transaction(source_name, target_doc=None):
	doc = get_mapped_doc("Bulk Outward Bank Payment", source_name,	{
		"Bulk Outward Bank Payment": {
			"doctype": "Bulk Outward Bank Payment",
			"field_map": {
				"company": "company",
				"company_bank_account": "company_bank_account",
				"reconcile_action": "reconcile_action",
				"transaction_type": "transaction_type"
			}
			},
		"Outward Bank Payment Details":{
			"doctype": "Outward Bank Payment Details",
			"field_map": {
				"party_type": "party_type",
				"party": "party",
				"amount": "amount"
			},
			"condition": lambda doc: doc.status not in ['Initiated', 'Transaction Completed']
		},
		}, target_doc)
	return doc