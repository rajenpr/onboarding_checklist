from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import subprocess
from datetime import datetime, timedelta
from pymongo import MongoClient
from subprocess import run
from subprocess import getoutput
import ldap3
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# MongoDB setup
client = MongoClient("mongodb://localhost:27017")
db = client.onboarding_check_db
onboarding_collection = db.onboarding

# LDAP Configuration
LDAP_SERVER = 'ldap://adbihldap.adbidesign.analog.com'
LDAP_BASE_DN = 'ou=Users,ou=global,dc=analog,dc=com'

def ldap_authenticate(username, password):
    """Authenticate user against LDAP server"""
    try:
        server = ldap3.Server(LDAP_SERVER, use_ssl=False)
        user_dn = f'uid={username},{LDAP_BASE_DN}'
        conn = ldap3.Connection(server, user=user_dn, password=password)

        if conn.bind():
            conn.unbind()
            return True
        return False
    except Exception as e:
        print(f"LDAP authentication error: {e}")
        return False

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def send_email(to_address, subject, body, cc_addresses=[], attachment=None):
    """Send email with optional attachment"""
    from_address = "no-reply@analog.com"
    default_cc = "eis-helpdesk@analog.com"
    cc_list = [default_cc] + [email.strip() for email in cc_addresses if email.strip()]
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Cc'] = ', '.join(cc_list)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    if attachment:
        attachment_path = os.path.join('/opt/onboardingdoc/', attachment)
        if os.path.exists(attachment_path):
            filename = os.path.basename(attachment)
            attachment_file = open(attachment_path, "rb")
            p = MIMEBase('application', 'octet-stream')
            p.set_payload((attachment_file).read())
            encoders.encode_base64(p)
            p.add_header('Content-Disposition', f"attachment; filename= {filename}")
            msg.attach(p)
        else:
            print(f"Attachment file not found: {attachment_path}")
            return False

    try:
        server = smtplib.SMTP('mail.analog.com')
        text = msg.as_string()
        print("Email Subject:", subject)
        print("Email To:", to_address)
        server.sendmail(from_address, [to_address] + cc_list, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Email sending error: {e}")
        return False

def find_manager_email(uid):
    """Find manager email from LDAP"""
    manager_dn = subprocess.getoutput(f"ldapsearch -xLLb ou=global,dc=analog,dc=com uid={uid} manager | grep manager").strip()
    if not manager_dn:
        return None
    manager_cn = manager_dn.split("CN=")[1].split(",")[0].replace("\\2C ", ", ")
    manager_email = subprocess.getoutput(rf"ldapsearch -xLLLL -H ldap://nwd2dc1.ad.analog.com -D svc_linux_onboarding@ad.analog.com -w '6vDz5wzn{{GnWBd6gUbKX\00rc' -b dc=ad,dc=analog,dc=com '(cn={manager_cn})' mail | grep mail").strip()
    if manager_email:
        email = manager_email.split(":")[1].strip()
        return email
    return None

def vdi_check(userid):
    """Check VDI availability for user"""
    vdi_loc = []
    sdc_domain = ['adbldesign', 'adbvdesign', 'adgtdesign', 'adsdesign', 'adsiv', 'bdcdesign', 'caidesign', 'csdesign', 'engus1', 'istdesign', 'mundesign', 'valdesign', 'engeu1']
    for loc in sdc_domain:
        vdi_host = userid + '-lx01.' + loc
        ping_out = run(['ping', '-c 2', vdi_host], capture_output=True)
        if ping_out.returncode == 0:
            vdi_loc.append(loc)
    return vdi_loc

def nobackup_check(uid):
    """Check nobackup area availability"""
    nobackup_loc = []
    sdc = ['adbldesign', 'adbvdesign', 'adgtdesign', 'ads', 'adsiv', 'bdc', 'caidesign', 'csdesign', 'engus1', 'gbo', 'istdesign', 'mundesign', 'njdesign', 'valdesign', 'engeu1']
    for loc in sdc:
        nis_nobackup_map = getoutput("ldapsearch -xLLL -b nisMapName=auto.nobackup,ou=automounts,ou=" + loc + ",ou=nis,dc=analog,dc=com cn=" + uid + "| grep nisMapEntry:")
        if nis_nobackup_map:
            nobackup_loc.append(loc)
    return nobackup_loc

def home_check(uid):
    """Check home directory availability"""
    home_loc = []
    sdc = ['adbldesign', 'adbvdesign', 'adgtdesign', 'ads', 'adsiv', 'bdc', 'caidesign', 'csdesign', 'engus1', 'gbo', 'istdesign', 'mundesign', 'njdesign', 'valdesign', 'engeu1']
    for loc in sdc:
        nis_home_map = getoutput("ldapsearch -xLLL -b nisMapName=auto.home,ou=automounts,ou=" + loc + ",ou=nis,dc=analog,dc=com cn=" + uid + "| grep nisMapEntry:")
        if nis_home_map:
            home_loc.append(loc)
    return home_loc

def contractor_check(uid):
    """Check if user is contractor and has DG profile"""
    cmd = "ldapsearch -xLLL -b ou=global,dc=analog,dc=com uid=" + uid + "|grep -v gecos|egrep 'Contractor|Vendor' &> /dev/null"
    exit_status = os.system(cmd)
    if exit_status != 0:
        return 2
    else:
        cmd = 'ssh adbldgtest-lx02.adbldesign.analog.com ls -l /dgagent/dglists|grep ' + uid + ' &> /dev/null'
        exit_status_xml = os.system(cmd)
    return exit_status_xml

def generate_email_body(uid, vdi_loc):
    """Generate email body for onboarding"""
    vpn_dict = {
        'adbldesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Bangalore.zip',
        'adbvdesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Limerick.zip',
        'adgtdesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Cavite.zip',
        'adsdesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Wilmington.zip',
        'adsiv': 'https://download.analog.com/entsectools/SDC_VPN_Client/SanJose.zip',
        'bdcdesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Beijing.zip',
        'caidesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Cairo.zip',
        'csdesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Colorado.zip',
        'engus1': 'https://download.analog.com/entsectools/SDC_VPN_Client/Ashburn.zip',
        'mundesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Munich.zip',
        'valdesign': 'https://download.analog.com/entsectools/SDC_VPN_Client/Valencia.zip',
        'engeu1': 'https://download.analog.com/entsectools/SDC_VPN_Client/Milan.zip'
    }
    etx_dict = {
        'adbldesign': 'https://etx.adbldesign.analog.com',
        'adbvdesign': 'https://etx.adbvdesign.analog.com',
        'adgtdesign': 'https://etx.adgtdesign.analog.com',
        'adsdesign': 'https://etx.adsdesign.analog.com',
        'adsiv': 'https://etx.adsiv.analog.com',
        'bdcdesign': 'https://etx.bdcdesign.analog.com',
        'caidesign': 'https://etx.caidesign.analog.com',
        'csdesign': 'https://etx.csdesign.analog.com',
        'engus1': 'https://etx.engus1.analog.com',
        'mundesign': 'https://etx.mundesign.analog.com',
        'valdesign': 'https://etx.valdesign.analog.com',
        'engeu1': 'https://etx.engeu1.analog.com/'
    }

    name = getoutput("ldapsearch -xLLL -b ou=global,dc=analog,dc=com uid=" + uid + "|grep gecos|cut -d ':' -f 2").strip().replace(".", " ")
    salutation = f"Hi {name},<br><br>"
    welcome = "<br>Welcome to ADI<br><br>"
    body = "Please refer to the following information to connect to the ADI Engineering Linux environment.<br><br>"
    body1 = "Please refer attached document for step-by-step instructions.<br><br>"
    body2 = f"Your Linux user id :<strong>{uid}</strong><br><br>"

    cmd = f"ldapsearch -xLLL -b ou=global,dc=analog,dc=com uid={uid} |grep -v gecos|egrep 'Contractor|Vendor' &> /dev/null"
    exit_status = os.system(cmd)
    if exit_status != 0:
        body3 = "You would have received a Linux password via Analog Email ID.<br><br>"
        body_alt = "Alternatively, use the link https://getcad.eng.analog.com/passreset to reset the Linux Password<br><br>"
    else:
        body3 = "Your Linux password is sent to your ADI reporting manager.<br><br>"
        body_alt = "Alternatively, use the link https://getcad.eng.analog.com/passreset to reset the Linux Password<br><br>"

    body4 = "Configure your mobile for DUO 2-factor authentication: https://confluence.analog.com/display/EEKMS/2FA+Enrollment<br><br>"
    body5 = "(You should be on the ADI network to access the above link)<br><br>"

    if len(vdi_loc) == 1:
        vdi_locat = vdi_loc[0]
        body6 = f"Install the SDC VPN Client on your PC from: {vpn_dict[vdi_locat]}<br><br>"
        body7 = "(Connect to the SDC VPN Client using windows credentials)<br><br>"
        body8 = f"Access your VDI through: {etx_dict[vdi_locat]}<br><br>"
    else:
        body6 = ""
        body7 = ""
        body8 = ""

    body9 = "(Use your Linux login-id in small letters and Linux password to login ETX)<br><br><br>"
    body10 = "<strong>Note</strong>: You need to login to your VDI within 60 days if not it will be deleted to conserve compute resource. <br><br>"
    body11 = "Regards,<br>"
    body12 = "EIS Heldesk"

    final_email_string = salutation + welcome + body + body1 + body2 + body3 + body_alt + body4 + body5 + body6 + body7 + body8 + body9 + body10 + body11 + body12
    return final_email_string

@app.route('/')
def index():
    """Redirect to login or home based on session"""
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with LDAP authentication"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        if ldap_authenticate(username, password):
            session.permanent = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/home')
@login_required
def home():
    """Main onboarding checklist page"""
    documents = [""] + (os.listdir('/opt/onboardingdoc/') if os.path.exists('/opt/onboardingdoc/') else [])
    return render_template('home.html', username=session['username'], documents=documents)

@app.route('/check_user', methods=['POST'])
@login_required
def check_user():
    """Process onboarding checklist for a user"""
    userid = request.form.get('userid', '').lower().strip()
    ritm_number = request.form.get('ritm_number', '').strip()
    cc_emails_input = request.form.get('cc_emails', '')
    cc_emails = [email.strip() for email in cc_emails_input.split(',') if email.strip()]
    selected_document = request.form.get('selected_document', '')

    if not userid:
        return jsonify({'error': 'User ID is required'}), 400

    results = {
        'userid': userid,
        'checks': []
    }

    # Check 1: LDAP Check
    output = run(["id", userid], capture_output=True, text=True)
    if output.returncode == 0:
        results['checks'].append({
            'name': 'Checking if user is in LDAP',
            'status': 'success',
            'message': 'User found in LDAP'
        })

        success_count = 1
        failure_count = 0

        # Check 2: VDI Check
        loc = vdi_check(userid)
        if len(loc) == 1:
            results['checks'].append({
                'name': 'VDI Check',
                'status': 'success',
                'message': f'User has one VDI available, it is in {loc[0]}'
            })
            success_count += 1
        elif len(loc) == 0:
            cmd = "ldapsearch -xLLL -b ou=global,dc=analog,dc=com uid=" + userid + "|grep -v gecos|egrep 'Vendor' &> /dev/null"
            exit_status = os.system(cmd)
            if exit_status == 0:
                results['checks'].append({
                    'name': 'VDI Check',
                    'status': 'success',
                    'message': 'User is a vendor and might not need dedicated VDI'
                })
                success_count += 1
            else:
                results['checks'].append({
                    'name': 'VDI Check',
                    'status': 'error',
                    'message': 'User has no VDI available, please deploy one'
                })
                failure_count += 1
        else:
            results['checks'].append({
                'name': 'VDI Check',
                'status': 'error',
                'message': f'User has more than one VDI available: {", ".join(loc)}, please ensure that the user has just one VDI'
            })
            failure_count += 1

        # Check 3: Nobackup check
        nobackup_loc = nobackup_check(userid)
        if len(nobackup_loc) >= 1:
            results['checks'].append({
                'name': 'Nobackup check',
                'status': 'success',
                'message': f'User has nobackup available at: {", ".join(nobackup_loc)}',
                'info': 'Owing to non-standard auto mount mapping types across sites (some offer user-specific maps while others have wildcard mapping), this information may not be accurate'
            })
        else:
            results['checks'].append({
                'name': 'Nobackup check',
                'status': 'warning',
                'message': "There isn't a nobackup area for the user, please get one created",
                'info': 'Owing to non-standard auto mount mapping types across sites (some sites offer user-specific maps while others have wildcard mapping), this information may not be accurate'
            })

        # Check 4: Home directory check
        home_loc = home_check(userid)
        if len(home_loc) >= 1:
            results['checks'].append({
                'name': 'Home directory check',
                'status': 'success',
                'message': f'User has home available at: {", ".join(home_loc)}'
            })
            success_count += 1
        else:
            results['checks'].append({
                'name': 'Home directory check',
                'status': 'error',
                'message': "There isn't a home area for the user, please get one created"
            })
            failure_count += 1

        # Check 5: DG profile check
        exit_status_xml = contractor_check(userid)
        if exit_status_xml == 0:
            results['checks'].append({
                'name': 'DG profile check',
                'status': 'success',
                'message': 'User is a contractor and .xml file is present on adbldgtest-lx02'
            })
            success_count += 1
        elif exit_status_xml == 2:
            results['checks'].append({
                'name': 'DG profile check',
                'status': 'info',
                'message': 'The user in question is an employee, so CAM info is not applicable. Skipping xml check.'
            })
            success_count += 1
        else:
            results['checks'].append({
                'name': 'DG profile check',
                'status': 'error',
                'message': 'User is a contractor/vendor but .xml file is not present on adbldgtest-lx02. Please execute the script to create DG profile and set up CAM portal'
            })
            failure_count += 1

        # Send email if all checks pass
        if success_count == 4:
            email_body = generate_email_body(userid, loc)
            email_address = subprocess.getoutput(f"ldapsearch -xLLb ou=global,dc=analog,dc=com uid={userid} | grep -i mail: | awk -F: '{{print $2}}'").strip()
            manager_email = find_manager_email(userid)
            if manager_email:
                cc_emails.append(manager_email)

            if send_email(email_address, "ADI Linux Onboarding", email_body, cc_addresses=cc_emails, attachment=selected_document):
                onboarding_collection.insert_one({"uid": userid, "RITM": ritm_number, "date": datetime.now()})
                results['email_sent'] = True
                results['message'] = 'Email sent and Onboarding logged in MongoDB.'
            else:
                results['email_sent'] = False
                results['message'] = 'Failed to send email.'
        else:
            results['email_sent'] = False
            results['message'] = 'There are some issues with the user, please check the above-mentioned errors and fix them before we can proceed with onboarding'

    else:
        results['checks'].append({
            'name': 'Checking if user is in LDAP',
            'status': 'error',
            'message': 'User not found, please check the uid entered by you or create the user using the Account management portal'
        })
        results['email_sent'] = False

    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
