# -*- coding: utf-8 -*-
# Copyright (c) 2021, Aerele and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import flt

class BulkOutwardBankPayment(Document):
	def validate(self):
		total_payment = 0
		for row in self.outward_bank_payment_details:
			total_payment+=flt(row.amount)
		self.total_payment = total_payment
		self.no_of_payments = len(self.outward_bank_payment_details)

	def on_submit(self):
		if self.status == 'Approved':
			for row in self.outward_bank_payment_details:
				doc = frappe.get_doc({'doctype': 'Outward Bank Payment',
				'party_type': row.party_type,
				'party': row.party,
				'amount': row.amount,
				'reconcile_action': self.reconcile_action,
				'bobp': self.name})
				doc.save()
				doc.submit()
				doc.db_set('workflow_state', 'Approved')