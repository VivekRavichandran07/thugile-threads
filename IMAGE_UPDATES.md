# Updating product images

## Replace photos for an already mapped product

1. Export five WebP images. Use the existing exact filenames, including capitalization (for example, `CitrusCharm1.webp` through `CitrusCharm5.webp`). Image 1 is the cover; 2–5 follow in the gallery.
2. Replace the files in `static/storefront/assets/Chudidar/`. Ignore files ending in `Zone.Identifier`; they are download metadata, not photos.
3. Commit and push the five image files to the branch used by your deployment, or deploy the updated checkout through your existing deployment workflow. Copying files locally does not update the live site.
4. After deployment completes, hard-refresh the storefront (Ctrl+Shift+R). Check the product card and all five photos on its product page. If stale photos persist, clear the browser/site cache and any configured CDN cache.

## First set of original photos for a product

Place five files using a consistent stem, for example `NewProduct1.webp` through `NewProduct5.webp`. Then register the product in these locations:

1. `app.py`: in `product_image_variants`, add `"newproduct": "NewProduct"` to `original_gallery`. The key is the product name in lowercase with spaces and punctuation removed.
2. `image_assets.py`: add `("New Product", "NewProduct1.webp")` to the cover mapping in `migrate_image_urls`. Use the exact catalog product name. This updates persisted product and wishlist covers on app startup without recreating products.
3. `static/storefront/script.js`: add `'New Product': '/static/storefront/assets/Chudidar/NewProduct1.webp'` to `imageMap` and add `NewProduct` to the numbered-image regular expression in `productImageVariants`.
4. Commit and deploy those three source files together with the five images. Check the cover and gallery after deployment.

For products with several sizes, the exact shared product name maps all sizes. Check that the photos belong to that product before registering them. Pista Aura still awaits its own original photos; Thalir uses `Thalir1.webp` through `Thalir5.webp`.
