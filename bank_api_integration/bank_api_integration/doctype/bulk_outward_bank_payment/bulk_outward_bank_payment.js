// Copyright (c) 2021, Aerele and contributors
// For license information, please see license.txt
{% include 'bank_api_integration/bank_api_integration/utils/js/common_fields.js' %};
frappe.ui.form.on("Bulk Outward Bank Payment", {
		refresh: function(frm) {
			frm.trigger('verify_and_initiate_payment');
			if(frappe.user.has_role('Bank Maker')){
				frm.set_df_property('retry_count', 'hidden', 1);
			}
			frm.trigger("show_summary");
			if (frm.doc.docstatus == 1 && frm.doc.workflow_state != 'Rejected'){
				if(frm.doc.__onload.initiated_txn_count ){
				frm.add_custom_button(__("Update Transaction Status"), function() {
				 frm.trigger('update_txn_status');
			 	}).addClass("btn-primary");
				}
				if(frm.doc.__onload.failed_doc_count){
				frm.add_custom_button(__("Recreate Failed Transactions"), function() {
					frm.trigger('recreate_failed_txn');
					 }).addClass("btn-primary");
					}
			}
		},
		before_workflow_action: function(frm){
			if(frm.selected_workflow_action == 'Reject'){
				return new Promise((resolve, reject) => {
					frappe.prompt({
						fieldtype: 'Data',
						label: __('Reason'),
						fieldname: 'reason'
					}, data => {
						frappe.call({
							method: "frappe.client.set_value",
							freeze: true,
							args: {
								doctype: 'Bulk Outward Bank Payment',
								name: frm.doc.name,
								fieldname: 'reason_for_rejection',
								value: data.reason,
							},
							callback: function(r) { 
								if (r.message) {
									resolve(r.message);
								} else {
									reject();
								}
							}
						});
					}, __('Reason for Rejection'), __('Submit'));
				})
		}
		},
		after_workflow_action: function(frm){
			if(frm.doc.workflow_state == 'Approved'){
			frappe.call({
				method: 'bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.get_field_status',
				freeze: true,
				args: {
					'bank_account': frm.doc.company_bank_account
				},
				callback: function(r) {
					let data = r.message;
					if (data) {
						if (!data.is_otp_enabled && !data.is_pwd_security_enabled){
							frappe.db.set_value('Bulk Outward Bank Payment', {'name': frm.doc.name},
							'workflow_state', 'Verified')
						}
					}
				}
			})
		}
			frm.trigger('verify_and_initiate_payment');
		},
		verify_and_initiate_payment: function(frm){
			if(frappe.user.has_role('Bank Checker') && frm.doc.workflow_state == 'Approved' && frm.doc.retry_count < 3){
				frm.add_custom_button(__("Verify and Initiate Payment"), function(){
				let dialog_fields = [];
				let bank_account = frm.doc.company_bank_account;
				frappe.call({
					   method: 'bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.get_field_status',
					   freeze: true,
					   args: {
						   'bank_account': bank_account
					   },
					   callback: function(r) {
						   let data = r.message;
						   if (data) {
							if (data.is_otp_enabled && !data.is_pwd_security_enabled){
								dialog_fields = [
									{
										fieldtype: "Int",
										label: __("OTP"),
										fieldname: "otp",
										reqd: 1
									}
								]
								show_dialog(frm, dialog_fields)
							}
							if (!data.is_otp_enabled && data.is_pwd_security_enabled){
								dialog_fields = [
									{
										fieldtype: "Password",
										label: __("Transaction Password"),
										fieldname: "transaction_password",
										reqd: 1
									}
								]
								show_dialog(frm, dialog_fields)
							}
							if (data.is_otp_enabled && data.is_pwd_security_enabled){
							frappe.call({
								method: 'bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.send_otp',
								freeze: true,
								args: {
									'doctype': 'Bulk Outward Bank Payment',
									'docname': frm.doc.name
								},
								callback: function(r) {
									if(r.message == true){
										frappe.show_alert({message:__('OTP Sent Successfully'), indicator:'green'});
										dialog_fields = [
												{
													fieldtype: "Password",
													label: __("Transaction Password"),
													fieldname: "transaction_password",
													reqd: 1
												},
												{
													fieldtype: "Int",
													label: __("OTP"),
													fieldname: "otp",
													reqd: 1
												}
											]
										show_dialog(frm, dialog_fields)
									}
								else{
									frappe.show_alert({message:__('Unable to send OTP'), indicator:'red'});
								}
								}})}
						   }
					   }
				   });
			   }).addClass("btn-primary");		
		}
		},
		company_bank_account: function(frm) {
			frappe.call({
				method: 'bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.get_transaction_type',
				args: {
					"bank_account":frm.doc.company_bank_account
				},
				freeze: true,
				callback: function(r) {
					if (r.message) {
						frm.set_df_property("transaction_type","options",r.message.join('\n'))
					}
				}
			});
		},
		recreate_failed_txn: function(){
			frappe.model.open_mapped_doc({
				method: "bank_api_integration.bank_api_integration.doctype.bulk_outward_bank_payment.bulk_outward_bank_payment.recreate_failed_transaction",
				frm: cur_frm,
				freeze_message: __("Fetching ...")
			})
		},
		update_txn_status: function(frm){
			frappe.call({
				method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.update_transaction_status",
				freeze: true,
				freeze_message: __("Processing..."),
				args: {bobp_name:frm.doc.name}
			})
		},
	show_summary: function(frm) {
		let transaction_summary = frm.doc.__onload.transaction_summary;
		if(frm.doc.workflow_state != 'Pending' && frm.doc.workflow_state != 'Rejected') {
			let section = frm.dashboard.add_section(
				frappe.render_template('bulk_outward_bank_payment', {
					data: transaction_summary
				})
			);
			frm.dashboard.show();
		}
	}
}
);
var show_dialog = function(frm, dialog_fields){
	let d = new frappe.ui.Dialog({
		title: __('Enter the Details'),
		fields: dialog_fields,
		primary_action: function() {
		 let data = d.get_values();
		 d.hide();
		 frappe.call({
			 method: 'bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.verify_and_initiate_transaction',
			 args: {
				 "doc":frm.doc,
				 "entered_password": data.transaction_password,
				 "otp": data.otp
			 },
			 freeze:true,
			 callback: function(r) {
				frm.reload_doc();
			 }
		 });
		}
	});
	d.show();
}
cur_frm.fields_dict.outward_bank_payment_details.grid.get_field("party_type").get_query  = function () {
	return {
		query: "erpnext.setup.doctype.party_type.party_type.get_party_type",
	};
}