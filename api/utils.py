from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_custom_email(subject, to_email, template_name, context):
    html_content = render_to_string(template_name, context)
    text_content = "This is an HTML email. Please view in an HTML-compatible client."

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=None,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


import base64
from io import BytesIO
from openpyxl import load_workbook
import magic  #from python-magic
from django.core.exceptions import ValidationError

def base64_to_excel_file(base64_str, filename="uploaded.xlsx"):
    try:
        # Step 1: Split and decode
        if ';base64,' not in base64_str:
            raise ValidationError("Invalid Uploaded file format.")

        _, file_str = base64_str.split(';base64,')
        decoded_file = base64.b64decode(file_str, validate=True)

        # Step 2: Validate file size
        if len(decoded_file) > 5 * 1024 * 1024:  # 5 MB limit
            raise ValidationError("File too large. For The Usage of this Service, please contact the Admin.")

        # Step 3: Check MIME type (to prevent disguised executables)
        mime_type = magic.from_buffer(decoded_file, mime=True)
        if mime_type not in [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ]:
            raise ValidationError("Invalid file type. Please upload an Excel file with the correct extension (.xlsx) (xls).")

        # Step 4: Try to load with openpyxl (checks structure and catches malformed Excel files)
        file_io = BytesIO(decoded_file)
        file_io.name = filename
        load_workbook(file_io)

        # Reset file pointer
        file_io.seek(0)
        return file_io

    except (base64.binascii.Error, ValueError):
        raise ValidationError("Invalid Uploaded file format. Please upload an Excel file with the correct extension (.xlsx) (xls) and no spaces in the filename.")
    except Exception as e:
        print(f'Error processing Excel file: {e}')
        raise ValidationError(f"Error processing Excel file: {str(e)}")


import re

# Common words to ignore in acronym generation
STOPWORDS = {"the", "of", "an", "in", "a", "and"}

def generate_acronym(name):
    # Remove extra spaces and convert to uppercase
    name = re.sub(r'\s+', ' ', name.strip()).upper()

    # Split name into words, filter out stopwords
    words = [word for word in name.split() if word.lower() not in STOPWORDS]

    # Create an acronym by taking the first letter of each word
    acronym = ''.join(word[0] for word in words if word)

    return acronym