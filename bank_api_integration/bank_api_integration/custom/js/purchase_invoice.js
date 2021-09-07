frappe.ui.form.on('Purchase Invoice', {
    refresh : function(frm){
        if(frm.doc.docstatus == 1 && frm.doc.outstanding_amount != 0
        && !(frm.doc.is_return && frm.doc.return_against)) {
            // Creating Make Bank Payment Button
            frm.add_custom_button(__('Make Bank Payment'), () =>{
            frm.trigger("make_bank_payment");
         },__('Create'));
    }
    },
    make_bank_payment : function(frm) {
        frappe.model.open_mapped_doc({
        method: "bank_api_integration.bank_api_integration.doctype.outward_bank_payment.outward_bank_payment.make_bank_payment",
        frm: frm
    })
},
});