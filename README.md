# Thugile Website

## Cashfree hosted checkout

Cashfree settings are loaded from the project-root `.env` file when the Flask app starts. The integration defaults to sandbox; use `CASHFREE_ENV=production` only with production credentials. Keep the secret key server-side; `.env` is ignored by Git.

```text
CASHFREE_APP_ID=...
CASHFREE_SECRET_KEY=...
CASHFREE_ENV=sandbox
CASHFREE_REDIRECT_BASE_URL=https://your-public-site.example
```

`CASHFREE_REDIRECT_BASE_URL` **must be set to your public HTTPS URL** for production deployments. Cashfree requires all return URLs to use HTTPS; without this variable set correctly, the API will reject payment requests with `order_meta.return_url_invalid`. The app will attempt to auto-detect the return URL from the request if this variable is omitted, but this may fail if the incoming request is via HTTP (e.g., behind a proxy or CDN). A URL path prefix is supported, and sandbox may use an HTTP localhost URL. Whitelist the checkout domain in Cashfree before accepting live payments. The app verifies order status with Cashfree before confirming an order.

## Deploy to Railway

Railway detects this Python/Flask app and uses `railway.json` to run it with Gunicorn and check `/health`. To deploy from a local checkout, install and log in to the [Railway CLI](https://docs.railway.com/guides/cli), run `railway init` from the project root, then `railway up`. Alternatively, create a service from a connected GitHub repository.

Before deploying, attach a Railway volume to the service at `/data`. Set these service variables in Railway (do not upload `.env` or commit credentials):

```text
DATABASE_PATH=/data/inventory.db
UPLOAD_FOLDER=/data/uploads
SECRET_KEY=<a-long-random-secret>
CASHFREE_ENV=sandbox
CASHFREE_APP_ID=<sandbox-app-id>
CASHFREE_SECRET_KEY=<sandbox-secret-key>
CASHFREE_REDIRECT_BASE_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=thugile.official@gmail.com
SMTP_PASSWORD=<Google-app-password>
CONTACT_EMAIL=thugile.official@gmail.com
```

Generate `SECRET_KEY` locally with `python -c "import secrets; print(secrets.token_hex(32))"` and paste the output into Railway. For production, set `CASHFREE_REDIRECT_BASE_URL` to your custom domain (e.g., `https://thugilethreads.store`), and whitelist that domain in the Cashfree dashboard.

The contact form sends messages through Gmail SMTP. Use port `465` for implicit TLS or `587` for STARTTLS; the application selects the correct TLS mode from `SMTP_PORT`. Create a Google App Password for `SMTP_USERNAME` (Google Account → Security → 2-Step Verification → App passwords), then add it as `SMTP_PASSWORD` in Railway; do not use your normal Gmail password or commit the app password. Set `CONTACT_EMAIL` to the inbox that should receive messages. Redeploy the service after adding or changing these variables.

The service stores its SQLite database and uploaded images under `/data`; without the volume these files are ephemeral. If you want to retain the current local catalog, stock, orders, and uploaded product images, upload `inventory.db` to the volume as `/inventory.db` and `static/uploads/` as `/uploads/` before accepting orders. Stop the service while replacing its SQLite database, then start/redeploy it. Existing `inventory.db` and uploads are not automatically transferred by deploying the source.

Keep the service to one replica while it uses SQLite. Before making the site public, protect `/admin/` and its mutation endpoints with an administrator-only role: the current app checks for a signed-in user, but does not distinguish administrators from customer accounts.



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/user/project/repository/web_editor/#create-a-file) or [upload](https://docs.gitlab.com/user/project/repository/web_editor/#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.com/rvivek0705/thugile-website.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://gitlab.com/rvivek0705/thugile-website/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/user/project/merge_requests/creating_merge_requests/)
* [Automatically close issues from merge requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/topics/autodevops/requirements/)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ci/environments/protected_environments/)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
