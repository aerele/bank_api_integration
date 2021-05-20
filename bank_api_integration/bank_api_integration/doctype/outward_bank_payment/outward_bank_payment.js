// Copyright (c) 2021, Aerele and contributors
// For license information, please see license.txt
{% include 'bank_api_integration/bank_api_integration/utils/common_fields.js' %};
frappe.ui.form.on('Outward Bank Payment', {
	onload: function(frm){
		if(frappe.user.has_role("Bank Checker")){ 
			frm.set_df_property('transaction_password', 'hidden', 0);
			frm.toggle_reqd("transaction_password", true);
		} 
		else{
			frm.set_df_property('transaction_password', 'hidden', 1);
			frm.toggle_reqd("transaction_password", false);
		}
		frm.refresh_fields("transaction_password");
	},
	refresh: function(frm) {
		if (frm.doc.docstatus == 1 && frm.doc.status == 'Initiated'){ 
			frm.add_custom_button(__("Update Transaction Status"), function() {
			 frm.trigger('update_txn_status');
		 });}
	},
	update_txn_status: function(frm){
		frappe.call({
			method: "bank_api_integration.bank_api_integration.doctype.outward_bank_payment.outward_bank_payment.update_transaction_status",
			freeze: true,
            args: {obp_name:frm.doc.name}
		})
	},
	after_workflow_action: (frm) => {
		if(frm.doc.workflow_state == "Rejected"){
		frm.set_value("status", "Pending");
		var me = this;
		var d = new frappe.ui.Dialog({
			title: __('Reason for Rejection'),
			fields: [
				{
					"fieldname": "reason_for_rejection",
					"fieldtype": "Data",
					"reqd": 1,
				}
			],
			primary_action: function() {
				var data = d.get_values();
				frappe.call({
					method: "frappe.desk.form.utils.add_comment",
					args: {
						reference_doctype: me.frm.doctype,
						reference_name: me.frm.docname,
						content: __('Reason for Rejection: ')+data.reason_for_rejection,
						comment_email: frappe.session.user,
						comment_by: frappe.session.user_fullname
					},
					callback: function(r) {
						if(!r.exc) {
							frm.set_value("status", "Rejected");
							frm.save('Update');
							d.hide();
						}
					}
				});
			}
		});
		d.show();

		}
	},
	get_outstanding_invoice: function(frm) {
		const today = frappe.datetime.get_today();
		const fields = [
			{fieldtype:"Section Break", label: __("Posting Date")},
			{fieldtype:"Date", label: __("From Date"),
				fieldname:"from_posting_date", default:frappe.datetime.add_days(today, -30)},
			{fieldtype:"Column Break"},
			{fieldtype:"Date", label: __("To Date"), fieldname:"to_posting_date", default:today},
			{fieldtype:"Section Break", label: __("Due Date")},
			{fieldtype:"Date", label: __("From Date"), fieldname:"from_due_date"},
			{fieldtype:"Column Break"},
			{fieldtype:"Date", label: __("To Date"), fieldname:"to_due_date"},
			{fieldtype:"Section Break", label: __("Outstanding Amount")},
			{fieldtype:"Float", label: __("Greater Than Amount"),
				fieldname:"outstanding_amt_greater_than", default: 0},
			{fieldtype:"Column Break"},
			{fieldtype:"Float", label: __("Less Than Amount"), fieldname:"outstanding_amt_less_than"},
			{fieldtype:"Section Break"},
			{fieldtype:"Check", label: __("Allocate Payment Amount"), fieldname:"allocate_payment_amount", default:1},
		];

		frappe.prompt(fields, function(filters){
			frappe.flags.allocate_payment_amount = true;
			frm.events.validate_filters_data(frm, filters);
			frm.events.get_outstanding_documents(frm, filters);
		}, __("Filters"), __("Get Outstanding Documents"));
	},

	validate_filters_data: function(frm, filters) {
		const fields = {
			'Posting Date': ['from_posting_date', 'to_posting_date'],
			'Due Date': ['from_posting_date', 'to_posting_date'],
			'Advance Amount': ['from_posting_date', 'to_posting_date'],
		};

		for (let key in fields) {
			let from_field = fields[key][0];
			let to_field = fields[key][1];

			if (filters[from_field] && !filters[to_field]) {
				frappe.throw(__("Error: {0} is mandatory field",
					[to_field.replace(/_/g, " ")]
				));
			} else if (filters[from_field] && filters[from_field] > filters[to_field]) {
				frappe.throw(__("{0}: {1} must be less than {2}",
					[key, from_field.replace(/_/g, " "), to_field.replace(/_/g, " ")]
				));
			}
		}
	},

	get_outstanding_documents: function(frm, filters) {
		frm.clear_table("payment_references");

		if(!frm.doc.party) {
			return;
		}
		var args = {
			"posting_date": frappe.datetime.get_today(),
			"company": frm.doc.company,
			"party_type": frm.doc.party_type,
			"payment_type": 'Pay',
			"party": frm.doc.party
		}

		for (let key in filters) {
			args[key] = filters[key];
		}

		frappe.flags.allocate_payment_amount = filters['allocate_payment_amount'];

		return  frappe.call({
			method: 'bank_api_integration.bank_api_integration.doctype.outward_bank_payment.outward_bank_payment.get_outstanding_reference_documents',
			args: {
				args:args
			},
			callback: function(r, rt) {
				console.log(r.message);
				if(r.message) {
					var total_positive_outstanding = 0;
					var total_negative_outstanding = 0;

					$.each(r.message, function(i, d) {
						var c = frm.add_child("payment_references");
						c.reference_doctype = d.voucher_type;
						c.reference_name = d.voucher_no;
						c.due_date = d.due_date
						c.total_amount = d.invoice_amount;
						c.outstanding_amount = d.outstanding_amount;
						c.bill_no = d.bill_no;

						if(!in_list(["Sales Order", "Purchase Order", "Expense Claim", "Fees"], d.voucher_type)) {
							if(flt(d.outstanding_amount) > 0)
								total_positive_outstanding += flt(d.outstanding_amount);
							else
								total_negative_outstanding += Math.abs(flt(d.outstanding_amount));
						}
						c.exchange_rate = 1;
						if (in_list(['Sales Invoice', 'Purchase Invoice', "Expense Claim", "Fees"], d.reference_doctype)){
							c.due_date = d.due_date;
						}
					});
				}
				frm.events.allocate_party_amount_against_ref_docs(frm,
					(frm.doc.amount));
				console.log(frm.doc.payment_references);
				refresh_field('payment_references');
			}
		});
	},
	allocate_party_amount_against_ref_docs: function(frm, paid_amount) {
		var total_positive_outstanding_including_order = 0;
		var total_negative_outstanding = 0;
		
		$.each(frm.doc.references || [], function(i, row) {
			if(flt(row.outstanding_amount) > 0)
				total_positive_outstanding_including_order += flt(row.outstanding_amount);
			else
				total_negative_outstanding += Math.abs(flt(row.outstanding_amount));
		})

		var allocated_negative_outstanding = 0;
		if (
				(frm.doc.payment_type=="Pay" && frm.doc.party_type=="Supplier") ||
				(frm.doc.payment_type=="Pay" && frm.doc.party_type=="Employee")
			) {
				if(total_positive_outstanding_including_order > paid_amount) {
					var remaining_outstanding = total_positive_outstanding_including_order - paid_amount;
					allocated_negative_outstanding = total_negative_outstanding < remaining_outstanding ?
						total_negative_outstanding : remaining_outstanding;
			}

			var allocated_positive_outstanding =  paid_amount + allocated_negative_outstanding;
		} else if (in_list(["Customer", "Supplier"], frm.doc.party_type)) {
			console.log(paid_amount, total_negative_outstanding);
			if(paid_amount > total_negative_outstanding) {
				if(total_negative_outstanding == 0) {
					frappe.msgprint(__("Cannot {0} {1} {2} without any negative outstanding invoice",
						['Pay',
							(frm.doc.party_type=="Customer" ? "to" : "from"), frm.doc.party_type]));
					return false
				} else {
					frappe.msgprint(__("Paid Amount cannot be greater than total negative outstanding amount {0}", [total_negative_outstanding]));
					return false;
				}
			} else {
				allocated_positive_outstanding = total_negative_outstanding - paid_amount;
				allocated_negative_outstanding = paid_amount +
					(total_positive_outstanding_including_order < allocated_positive_outstanding ?
						total_positive_outstanding_including_order : allocated_positive_outstanding)
			}
		}

		$.each(frm.doc.references || [], function(i, row) {
			row.allocated_amount = 0 //If allocate payment amount checkbox is unchecked, set zero to allocate amount
			if(frappe.flags.allocate_payment_amount != 0){
				if(row.outstanding_amount > 0 && allocated_positive_outstanding > 0) {
					if(row.outstanding_amount >= allocated_positive_outstanding) {
						row.allocated_amount = allocated_positive_outstanding;
					} else {
						row.allocated_amount = row.outstanding_amount;
					}

					allocated_positive_outstanding -= flt(row.allocated_amount);
				} else if (row.outstanding_amount < 0 && allocated_negative_outstanding) {
					if(Math.abs(row.outstanding_amount) >= allocated_negative_outstanding)
						row.allocated_amount = -1*allocated_negative_outstanding;
					else row.allocated_amount = row.outstanding_amount;

					allocated_negative_outstanding -= Math.abs(flt(row.allocated_amount));
				}
			}
		})

		frm.refresh_fields()
		frm.events.set_total_allocated_amount(frm);
	},

});
