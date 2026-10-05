# Security remediation and release

The local database and Python environments are untracked and ignored. Their local copies are preserved. Deploy with DATABASE_PATH pointing at a persistent private volume; back up the existing production database before releasing. A fresh checkout starts with an empty database and must not rely on a committed inventory.db.

Account lookup now returns only an exists boolean. This still reveals account existence to support the existing login/signup flow. New and reset passwords require ten characters. Existing passwords remain usable. Cart prices and Cashfree order totals are calculated from product IDs and database prices. Public product responses provide availability without exact stock counts.

The CSP restricts external scripts to Google sign-in and Cashfree, blocks objects and embedding, and restricts forms to this origin. Existing inline scripts, event handlers and styles require unsafe-inline; moving them to external files or nonces is further hardening. Verify Google sign-in and Cashfree hosted checkout in a browser after deployment.

## Historical database exposure

inventory.db exists in old commits. Untracking it does not erase that history or downloaded copies. Treat any real customer data previously stored there as exposed. Review incident obligations and invalidate affected credentials or sessions as appropriate.

History rewriting affects every collaborator and requires coordinated force pushes. Back up the repository and production data first. In a separate fresh mirror clone, use git-filter-repo to remove inventory.db from every historical path (including renamed copies), as well as venv/, vene/ and __pycache__/. Inspect the rewritten refs before force-pushing affected branches and tags. Collaborators should re-clone rather than merge old history back in. Request removal of cached historical database views from the repository host where applicable. No history rewrite or remote push has been performed by this patch.
