#!/usr/bin/env python3
"""Add Google Sign-In to all storefront auth pages."""
import os
import re

# Pages that need Google Sign-In added
pages = [
    "templates/checkout.html",
    "templates/collections.html",
    "templates/orders.html",
    "templates/privacy_policy.html",
    "templates/shipping.html",
    "templates/shipping_returns.html",
    "templates/terms.html",
    "templates/thugil_story_page.html",
    "templates/base.html",
]

google_script = '  <script src="https://accounts.google.com/gsi/client" async></script>\n'

google_ui = '''          <div style="margin:18px 0;text-align:center">
            <span style="display:inline-block;width:1px;height:1px;background:#ccc;border-radius:50%"></span>
            <span style="margin:0 10px;font-size:12px;color:#7a6e62;text-transform:uppercase;letter-spacing:.05em">or sign in with</span>
            <span style="display:inline-block;width:1px;height:1px;background:#ccc;border-radius:50%"></span>
          </div>
          <div id="g_id_onload" data-auto_prompt="false" data-callback="handleGoogleCredentialResponse" data-client_id="">
          </div>
          <div class="g_id_signin" style="margin-bottom:16px;text-align:center">
            <div id="google-button-container"></div>
          </div>'''

for page in pages:
    if not os.path.exists(page):
        print(f"⚠ {page} not found")
        continue
    
    with open(page, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Skip if already has Google Sign-In
    if 'g_id_onload' in content:
        print(f"✓ {page} already has Google Sign-In")
        continue
    
    # Add Google script to head if missing
    if 'accounts.google.com/gsi/client' not in content:
        content = content.replace('</head>', f'{google_script}</head>')
        print(f"✓ Added Google script tag to {page}")
    
    # Add Google UI to auth-step-1 before "By continuing" text
    # Find the auth-step-1 div and locate the "By continuing" paragraph
    pattern = r'(<!-- Step 1:.*?<form id="auth-identifier-form">.*?</form>)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        # Find where to insert (after the form, before "By continuing")
        insert_pos = content.find('<p style="margin:16px 0 0;font-size:12px;color:#7a6e62;text-align:center;">By continuing', match.start())
        if insert_pos > 0:
            content = content[:insert_pos] + google_ui + '\n' + content[insert_pos:]
            print(f"✓ Added Google Sign-In UI to {page}")
        else:
            print(f"⚠ Could not find insertion point in {page}")
    else:
        print(f"⚠ Could not find auth-step-1 form in {page}")
    
    with open(page, 'w', encoding='utf-8') as f:
        f.write(content)

print("\n✅ Done!")

