# Search engine setup for thugilethreads.store

The live homepage, robots.txt, and sitemap returned HTTP 200 during the check.
All seven sitemap pages were accessible without login and had no noindex directive.
These checks show crawl eligibility; they do not confirm Google indexing or ranking.

## Google

1. Open https://search.google.com/search-console/welcome and sign in with the Google account that should own the site.
2. Add a **URL prefix** property for `https://thugilethreads.store/`.
3. Choose **HTML tag** under the verification methods. Copy the complete meta tag.
4. Set `GOOGLE_SITE_VERIFICATION` in Railway to only the tag's `content` value, then deploy the updated code. Alternatively, provide the tag in this chat for help configuring it. Do not use `GOOGLE_CLIENT_ID`: Google login and search verification are separate settings.
5. Check the live homepage source for the verification tag, then click **Verify** in Search Console. Keep the setting in place after verification.
6. In **Sitemaps**, submit `https://thugilethreads.store/sitemap.xml`.
7. In **URL inspection**, inspect `https://thugilethreads.store/`, run the live test, and choose **Request indexing** if available. Repeat for `/shop/collections` and `/shop/our-story`.
8. Review the Pages and Sitemaps reports for crawl or indexing errors. Google decides whether and when to index; submissions do not guarantee a search result or position.

A Domain property is also supported by Google, but requires adding Google's TXT record at the domain's DNS provider. The app's HTML meta tag method applies to URL-prefix properties.

## Bing

1. Open https://www.bing.com/webmasters/ and sign in.
2. Import the verified Google Search Console property, or add `https://thugilethreads.store/` manually.
3. For manual HTML meta verification, set `BING_SITE_VERIFICATION` in Railway to the `content` value of Bing's `msvalidate.01` meta tag, deploy, and verify.
4. Submit `https://thugilethreads.store/sitemap.xml` in Bing's Sitemaps screen.

## Already configured in the app

- Public sitemap with seven canonical pages and a robots.txt sitemap pointer.
- Canonical URLs, page titles/descriptions, and social metadata.
- Product structured data and homepage WebSite structured data with the brand name.
- Checkout, account, password reset, and payment-status pages marked noindex.
- Optional Google and Bing verification tags, read from the settings above.

## Official references

- https://support.google.com/webmasters/answer/9008080
- https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl
- https://www2.bing.com/webmasters/help/add-and-verify-site-12184f8b
