// Copyright (c) 2025, nabeel saleem
// For license information, please see license.txt

frappe.ui.form.on("Tax Exemption Certificate", {
  donor: function (frm) {
    fetch_total_donation(frm);
  },

  fiscal_year: function (frm) {
    fetch_total_donation(frm);
  },

  currency: function (frm) {
    if (frm.doc.donor && frm.doc.fiscal_year) {
      fetch_total_donation(frm);
    }
  },

  after_save: function (frm) {
    make_fields_readonly(frm);
  },

  refresh: function (frm) {
    if (!frm.is_new()) {
      make_fields_readonly(frm);
    }
  },
});

function make_fields_readonly(frm) {
  frm.set_df_property("donor", "read_only", 1);
  frm.set_df_property("fiscal_year", "read_only", 1);
  frm.set_df_property("date_of_issue", "read_only", 1);
}

// Validate that Date of Issue cannot be earlier than today
// function validate_date_of_issue(frm) {
//   if (!frm.doc.date_of_issue) return;

//   const today = frappe.datetime.nowdate();
//   if (frm.doc.date_of_issue < today) {
//     frappe.msgprint({
//       title: __("Invalid Date"),
//       message: __("Date of Issue cannot be earlier than today."),
//       indicator: "orange",
//     });
//     frm.set_value("date_of_issue", "");
//   }
// }

function formatInternationalNumber(value) {
  if (!value) return "0";
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

function fetch_total_donation(frm) {
  frm.set_value("total_donation", 0);

  if (!frm.doc.donor || !frm.doc.fiscal_year) return;

  // Get currency from form field or let backend fetch from donor's default_currency
  const currency = frm.doc.currency || null;

  frappe.call({
    method: "akfp_crm.akfp_crm.doctype.tax_exemption_certificate.tax_exemption_certificate.get_total_donation",
    args: {
      donor: frm.doc.donor,
      fiscal_year: frm.doc.fiscal_year,
      currency: currency,
    },
    callback: function (r) {
      if (!r.message) return;

      const { total_donation, message, currency: returned_currency, currency_symbol, show_currency_symbol } = r.message;

      if (total_donation) {
        // Update currency field if returned from backend
        if (returned_currency && !frm.doc.currency) {
          frm.set_value("currency", returned_currency);
        }
        
        const formatted = formatInternationalNumber(total_donation);
        if (show_currency_symbol && (currency_symbol || returned_currency)) {
          const sym = currency_symbol || returned_currency;
          frm.set_value("total_donation", `${sym} ${formatted}`);
        } else {
          frm.set_value("total_donation", formatted);
        }
      } else {
        frappe.msgprint({
          title: __("No Donations Found"),
          message: message || __("No paid donations found for the selected donor and fiscal year."),
          indicator: "orange",
        });
        frm.set_value("fiscal_year", "");
      }
    },
  });
}
