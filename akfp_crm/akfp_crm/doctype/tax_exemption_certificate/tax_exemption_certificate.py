# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import random
import string
import base64
import qrcode
import io
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, today
from frappe import _


class TaxExemptionCertificate(Document): 
    def validate(self):
        """Validate the certificate data before save"""
        # Validate that date_of_issue is not in the future
        if self.date_of_issue and self.date_of_issue > today():
            frappe.throw(
                _("Date of Issue cannot be a future date. Please select today or a past date."),
                title=_("Invalid Date")
            )
    
    def before_insert(self):
        # Auto-generate certificate number in format: TEX-2025-001
        if not self.certificate_number:
            current_year = now_datetime().year

            # Get the highest sequence number for current year
            last_cert = frappe.db.sql(
                """
                SELECT certificate_number 
                FROM `tabTax Exemption Certificate`
                WHERE certificate_number LIKE %s
                ORDER BY certificate_number DESC
                LIMIT 1
                """,
                (f"TEX-{current_year}-%",),
                as_dict=True,
            )

            if last_cert:
                last_number = int(last_cert[0].certificate_number.split("-")[-1])
                next_number = last_number + 1
            else:
                next_number = 1

            self.certificate_number = f"TEX-{current_year}-{next_number:03d}"

        if not self.generated_timestamp:
            self.generated_timestamp = now_datetime()

    def get_qr_code(self):
        """Generate a base64 QR code for this certificate"""
        url = get_url(f"/verify-certificate?name={self.name}")


        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_png = buf.getvalue()

        return "data:image/png;base64," + base64.b64encode(qr_png).decode()

    
@frappe.whitelist(allow_guest=True)
def verify_certificate(cert_no: str):

    cert = frappe.get_all(
        "Tax Exemption Certificate",
        filters={"certificate_number": cert_no},
        fields=[
            "name",
            "certificate_number",
            "donor",
            "donor_address",
            "donor_cnic__ntn",
            "donation_date",
            "date_of_issue",
            "total_donation",
            "payment_method",
            "generated_timestamp",
        ],
        limit=1,
    )

    if not cert:
        return {"valid": False, "message": "Certificate not found"}

    return {
        "valid": True,
        "certificate": cert[0],
    }


@frappe.whitelist(allow_guest=True)
def get_certificate_details(name: str):
    """Get certificate details by name for verification page"""
    try:
        cert = frappe.get_doc("Tax Exemption Certificate", name)
        
        return {
            "valid": True,
            "certificate": {
                "name": cert.name,
                "certificate_number": cert.certificate_number,
                "donor": cert.donor,
                "donor_name": cert.donor_name,
                "donor_address": cert.donor_address,
                "donor_cnic__ntn": cert.donor_cnic__ntn,
                "date_of_issue": cert.date_of_issue,
                "total_donation": cert.total_donation,
                "generated_timestamp": cert.generated_timestamp,
                "fiscal_year": cert.fiscal_year,
            }
        }
    except frappe.DoesNotExistError:
        return {
            "valid": False,
            "message": "Certificate not found"
        }
    except Exception as e:
        return {
            "valid": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_total_donation(donor, fiscal_year=None):
    """Return total donation for selected donor in selected fiscal year,
    considering only Paid donations (exclude pledges)."""

    if not donor:
        return {"total_donation": 0, "message": "Please select a donor first."}

    if not fiscal_year:
        return {"total_donation": 0, "message": "Please select a fiscal year."}

    # Get fiscal year range
    fy = frappe.db.get_value(
        "Fiscal Year",
        fiscal_year,
        ["year_start_date", "year_end_date"],
        as_dict=True,
    )

    if not fy:
        return {"total_donation": 0, "message": f"Fiscal Year '{fiscal_year}' not found."}

    # Sum only Paid donations
    data = frappe.db.sql(
        """
        SELECT SUM(pd.donation_amount) AS total_donation_amount
        FROM `tabPayment Detail` pd
        INNER JOIN `tabDonation` dn ON dn.name = pd.parent
        WHERE pd.donor = %s
          AND dn.due_date BETWEEN %s AND %s
          AND dn.docstatus = 1
          AND dn.status = 'Paid'
        """,
        (donor, fy.year_start_date, fy.year_end_date),
        as_dict=True,
    )

    total_donation = data[0].total_donation_amount if data and data[0].total_donation_amount else 0

    if total_donation == 0:
        return {
            "total_donation": 0,
            "message": f"No paid donations found for donor '{donor}' in fiscal year '{fiscal_year}'."
        }

    return {"total_donation": total_donation}


