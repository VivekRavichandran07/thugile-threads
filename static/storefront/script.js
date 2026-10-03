if (document.querySelector('.site-header')) {
  const socialLinks = [
    {
      label: 'Instagram',
      href: 'https://www.instagram.com/thugile_and_threads/',
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="17.6" cy="6.6" r="1.1" fill="currentColor"/></svg>',
      external: true
    },
    {
      label: 'Facebook',
      href: 'https://www.facebook.com/thugileandthreads',
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M13.5 21v-8h2.7l.4-3.1h-3.1v-2c0-.9.3-1.5 1.6-1.5h1.7V3.6c-.3 0-1.3-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2.1H7.3V13h2.8v8z"/></svg>',
      external: true
    },
    {
      label: 'WhatsApp',
      href: 'https://wa.me/c/230554632978683',
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.2 11.8a8.1 8.1 0 0 1-12 7.1L4 20l1.1-4a8.1 8.1 0 1 1 15.1-4.2Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M9 8.5c.2-.4.4-.4.7-.4h.4c.2 0 .3.1.4.4l.7 1.6c.1.2 0 .4-.1.6l-.5.6c-.2.2-.2.3 0 .6.5.8 1.1 1.4 1.9 1.8.3.2.4.2.6-.1l.7-.8c.2-.2.4-.2.6-.1l1.5.7c.2.1.3.2.3.4 0 .3-.2 1.1-.7 1.5-.4.4-1 .6-1.6.5-1-.2-2.2-.7-3.4-1.8-1-.9-1.7-2.1-1.9-3.1-.2-.7 0-1.4.4-1.9Z" fill="currentColor"/></svg>',
      external: true
    },
    {
      label: 'Email',
      href: 'mailto:thugile.official@gmail.com',
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m4 7 8 6 8-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      external: false
    }
  ];
  const socialRail = document.createElement('nav');
  socialRail.className = 'social-rail';
  socialRail.setAttribute('aria-label', 'Reach us');
  socialRail.innerHTML = socialLinks.map(({label, href, icon, external}) =>
    `<a class="social-rail-link social-rail-${label.toLowerCase()}" href="${href}" aria-label="${label}" title="${label}"${external ? ' target="_blank" rel="noopener noreferrer"' : ''}>${icon}</a>`
  ).join('');
  document.body.append(socialRail);
}

const count = document.querySelector('#bag-count');
const wishlistCount = document.querySelector('#wishlist-count');
const toast = document.querySelector('#toast');
const grid = document.querySelector('.products');
const productSort = document.getElementById('product-sort');
const newLaunchesTrack = document.getElementById('new-launches-track');
const bagBtn = document.querySelector('#bag-btn');
const cartSidebar = document.querySelector('#cart-sidebar');
const cartOverlay = document.querySelector('#cart-overlay');
const cartClose = document.querySelector('#cart-close');
const cartItems = document.querySelector('#cart-items');
const cartTotal = document.querySelector('#cart-total');
const checkoutBtn = document.querySelector('#checkout-btn');
const wishlistSidebar = document.querySelector('#wishlist-sidebar');
const wishlistOverlay = document.querySelector('#wishlist-overlay');
const wishlistClose = document.querySelector('#wishlist-close');
const wishlistItems = document.querySelector('#wishlist-items');
const productOverlay = document.getElementById('product-overlay');
const productPopup = document.getElementById('product-popup');
const productPopupClose = document.getElementById('product-popup-close');
const productMainImage = document.getElementById('product-main-image');
const productThumbnails = document.getElementById('product-thumbnails');
const productImageStack = document.getElementById('product-image-stack');
const productName = document.getElementById('product-popup-name');
const productPrice = document.getElementById('product-popup-price');
const productDesc = document.getElementById('product-popup-desc');
const productSizes = document.getElementById('product-popup-sizes');
const productAddToBag = document.getElementById('product-add-to-bag');
const productWishlistBtn = document.getElementById('product-wishlist-btn');
const searchBtn = document.querySelector('.search-btn');
const searchOverlay = document.getElementById('search-overlay');
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
const fallbackImages = [
  '/static/storefront/assets/Chudidar/image-1.png',
  '/static/storefront/assets/Chudidar/image-2.jpg',
  '/static/storefront/assets/Chudidar/image-3.jpg',
  '/static/storefront/assets/Chudidar/image-4.jpg'
];
var bag = [], toastTimer, currentProduct = null, currentImageIndex = 0, pendingCartItem = null, pendingWishlistItem = null, searchProducts = [];
const escapeHtml = value => String(value || '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const imageFor = (url, index, name) => {
  const imageMap = {
    'Sanganeri Block Print Kurta': '/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.png',
    'Ajrakh Co-ord Set': '/static/storefront/assets/Chudidar/AjrakhCoordSet.png',
    'Kalamkari Print Set': '/static/storefront/assets/Chudidar/KalamkariPrintSet.png',
    'Acharam Block Print Kurta': '/static/storefront/assets/Chudidar/AcharamBlockPrintKurta.png',
    'Vasantha Embroidery Set': '/static/storefront/assets/Chudidar/VasanthaEmbroiderySet.png',
    'Thalaikku Workwear': '/static/storefront/assets/Chudidar/ThalaikkuWorkwear.png',
    'Meenakari Embroidered Set': '/static/storefront/assets/Chudidar/MeenakariEmbroideredSet.png',
    'Thenral Cotton Co-ord': '/static/storefront/assets/Chudidar/ThenralCottonCoord.png',
    'Pavai Handloom Set': '/static/storefront/assets/Chudidar/PavaiHandloomSet.png',
    'Kongu Cotton Coord': '/static/storefront/assets/Chudidar/KonguCottonCoord.png',
    'Kanakavalli Silk Co-ord': '/static/storefront/assets/Chudidar/KanakavalliSilkCoord.png',
    'Thaai Silk Set': '/static/storefront/assets/Chudidar/ThaaiSilkSet.png',
    'Kongu Cotton Coord': '/static/storefront/assets/Chudidar/KonguCottonCoord.png',
    'Mayil Set': '/static/storefront/assets/Chudidar/ThaaiSilkSet.png',
    'Thamarai Set': '/static/storefront/assets/Chudidar/KalamkariPrintSet.png',
    'Vennila Set': '/static/storefront/assets/Chudidar/PavaiHandloomSet.png',
    'Manjal Set': '/static/storefront/assets/Chudidar/image-1.png',
    'Maragatham Set': '/static/storefront/assets/Chudidar/image-2.jpg',
    'Rosa Set': '/static/storefront/assets/Chudidar/Rosaset.png',
    'Neelam Set': '/static/storefront/assets/Chudidar/image-3.jpg',
    'Gulmohar Set': '/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.png',
    'KotaSet': '/static/storefront/assets/Chudidar/Kotaset1.png',
    'Mul Chanderi': '/static/storefront/assets/Chudidar/mul chanderi.png'
  };
  return imageMap[name] || (url && /^(?:https?:\/\/|\/)/i.test(url) ? url : fallbackImages[index % fallbackImages.length]);
};
const productImageVariants = image => {
  const match = String(image).match(/^(.*)\.([a-z0-9]+)$/i);
  if (!match || !match[1].includes('/static/storefront/assets/Chudidar/')) return [image];
  return [image, `${match[1]}-1.png`, `${match[1]}-2.png`, `${match[1]}-3.png`, `${match[1]}-4.png`];
};
const availableImageVariants = async image => {
  const candidates = productImageVariants(image);
  const results = await Promise.all(candidates.map(async candidate => {
    try {
      const response = await fetch(candidate, { method: 'HEAD' });
      return response.ok ? candidate : null;
    } catch {
      return null;
    }
  }));
  return results.filter(Boolean);
};
const rupees = value => `₹ ${Number(value).toLocaleString('en-IN', {minimumFractionDigits: 0, maximumFractionDigits: 2})}`;
const discountedPrice = (value, discounted) => Number(discounted || value || 0);
const priceMarkup = (value, discounted) => {
  const original = Number(value || 0);
  const sale = discountedPrice(original, discounted);
  return sale < original
    ? `<del>${rupees(original)}</del><strong>${rupees(sale)}</strong>`
    : `<strong>${rupees(original)}</strong>`;
};
const viewCounts = () => {
  try { return JSON.parse(localStorage.getItem('tnt_product_views') || '{}'); } catch { return {}; }
};
const trackProductView = name => {
  const counts = viewCounts();
  counts[name] = (Number(counts[name]) || 0) + 1;
  localStorage.setItem('tnt_product_views', JSON.stringify(counts));
};

function loadCart() {
  try {
    const saved = localStorage.getItem('tnt_cart');
    bag = mergeCartItems(saved ? JSON.parse(saved) : []);
  } catch {
    bag = [];
  }
  updateCartUI();
}

function mergeCartItems(items) {
  return items.reduce((merged, item) => {
    const size = item.size || 'M';
    const existing = merged.find(cartItem => cartItem.name === item.name && (cartItem.size || 'M') === size);
    if (existing) {
      existing.qty += Number(item.qty) || 0;
    } else {
      merged.push({
        ...item,
        size,
        price: Number(item.price) || 0,
        qty: Number(item.qty) || 1,
      });
    }
    return merged;
  }, []);
}

function saveCart() {
  bag = mergeCartItems(bag);
  localStorage.setItem('tnt_cart', JSON.stringify(bag));
  updateCartUI();
  syncCartToServer();
}

function updateCartUI() {
  bag = mergeCartItems(bag);
  const totalItems = bag.reduce((sum, item) => sum + item.qty, 0);
  if (count) count.textContent = totalItems;
  renderCartItems();
}

function cartQuantityControls(item, index) {
  return `<div class="cart-quantity" role="group" aria-label="Quantity for ${escapeHtml(item.name)}">
    <button type="button" data-cart-quantity="-1" data-idx="${index}" aria-label="Decrease quantity" ${item.qty <= 1 ? 'disabled' : ''}>−</button>
    <output aria-label="Quantity" aria-live="polite">${item.qty}</output>
    <button type="button" data-cart-quantity="1" data-idx="${index}" aria-label="Increase quantity" ${item.qty >= 100 ? 'disabled' : ''}>+</button>
  </div>`;
}

function changeCartQuantity(index, delta) {
  if (!Number.isInteger(index) || !bag[index] || ![-1, 1].includes(delta)) return;
  const quantity = Math.max(1, Math.min(100, Number(bag[index].qty) + delta));
  if (quantity === bag[index].qty) return;
  bag[index].qty = quantity;
  saveCart();
  if (document.getElementById('checkout-items')) renderCheckout(false);
}

document.addEventListener('click', event => {
  const button = event.target.closest('button[data-cart-quantity]');
  if (!button || button.disabled) return;
  changeCartQuantity(Number(button.dataset.idx), Number(button.dataset.cartQuantity));
});

function renderCartItems() {
  if (!cartItems) return;
  if (!checkoutBtn) return;
  if (!bag.length) {
    cartItems.innerHTML = '<p class="cart-empty">Your bag is empty.</p>';
    if (cartTotal) cartTotal.textContent = '₹ 0';
    checkoutBtn.disabled = true;
    return;
  }
  checkoutBtn.disabled = false;
  const total = bag.reduce((sum, item) => sum + (item.price * item.qty), 0);
  if (cartTotal) cartTotal.textContent = rupees(total);
  cartItems.innerHTML = bag.map((item, idx) => `
    <div class="cart-item">
      <img src="${escapeHtml(imageFor(item.image_url, idx, item.name))}" alt="${escapeHtml(item.name)}" class="cart-item-image">
      <div class="cart-item-info">
        <p class="cart-item-name">${escapeHtml(item.name)}</p>
        <p class="cart-item-meta">Size: ${item.size || 'M'} · ${rupees(item.price)} each</p>
        ${cartQuantityControls(item, idx)}
        <button class="cart-item-remove" data-idx="${idx}">Remove</button>
      </div>
      <strong>${rupees(item.price * item.qty)}</strong>
    </div>
  `).join('');
}

function addToBag(name, price, size, image_url, quantity = 1) {
  if (!currentUser) {
    pendingCartItem = { name, price: Number(price), size: size || null, image_url: image_url || null, quantity };
    openAuthModal();
    return;
  }
  const existing = bag.find(item => item.name === name && (item.size || 'M') === (size || 'M'));
  if (existing) {
    existing.qty += quantity;
  } else {
    bag.push({ name, price: Number(price), qty: quantity, size: size || null, image_url: image_url || null });
  }
  saveCart();
  toast.textContent = `${name} added to your bag`;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}

function removeFromBag(index) {
  bag.splice(index, 1);
  saveCart();
}

function openCart() {
  if (cartSidebar) cartSidebar.classList.add('open');
  if (cartOverlay) cartOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeCart() {
  if (cartSidebar) cartSidebar.classList.remove('open');
  if (cartOverlay) cartOverlay.classList.remove('open');
  document.body.style.overflow = '';
}

function openWishlist() {
  if (wishlistSidebar) wishlistSidebar.classList.add('open');
  if (wishlistOverlay) wishlistOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
  renderWishlistItems();
}

function closeWishlist() {
  if (wishlistSidebar) wishlistSidebar.classList.remove('open');
  if (wishlistOverlay) wishlistOverlay.classList.remove('open');
  document.body.style.overflow = '';
}

function renderWishlistItems() {
  if (!wishlistItems) return;
  const items = getWishlist();
  if (!items.length) {
    wishlistItems.innerHTML = '<p class="wishlist-empty">Your wishlist is empty.</p>';
    return;
  }
  wishlistItems.innerHTML = items.map(item => `
    <div class="wishlist-item">
      <img src="${escapeHtml(imageFor(item.image_url, 0, item.name))}" alt="${escapeHtml(item.name)}" class="wishlist-item-image">
      <div class="wishlist-item-info">
        <p class="wishlist-item-name">${escapeHtml(item.name)}</p>
        <p class="wishlist-item-meta">${rupees(item.price)}</p>
        <button class="move-to-cart-btn" data-name="${escapeHtml(item.name)}" data-price="${item.price}" data-image="${escapeHtml(item.image_url)}">Move to cart</button>
      </div>
    </div>
  `).join('');

  wishlistItems.querySelectorAll('.move-to-cart-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const name = btn.dataset.name;
      const price = Number(btn.dataset.price);
      const image_url = btn.dataset.image || null;
      addToBag(name, price, null, image_url);
      const items = getWishlist();
      const idx = items.findIndex(i => i.name === name);
      if (idx >= 0) {
        items.splice(idx, 1);
        saveWishlist(items);
        renderWishlistItems();
      }
      toast.textContent = `${name} moved to your bag`;
      toast.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    });
  });
}

function getWishlist() {
  try {
    const saved = localStorage.getItem('tnt_wishlist');
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
}

function saveWishlist(items) {
  localStorage.setItem('tnt_wishlist', JSON.stringify(items));
  updateWishlistUI();
  syncWishlistToServer();
}

function updateWishlistUI() {
  const items = getWishlist();
  if (wishlistCount) {
    wishlistCount.textContent = items.length;
  }
  if (currentProduct && productWishlistBtn) {
    const isWished = items.some(i => i.name === currentProduct.name);
    productWishlistBtn.classList.toggle('wishlisted', isWished);
    productWishlistBtn.querySelector('.wishlist-icon').textContent = isWished ? '♥' : '♡';
    productWishlistBtn.querySelector('.wishlist-text').textContent = isWished ? 'Wishlisted' : 'Add to wishlist';
  }
}

function toggleWishlist(product) {
  if (!currentUser) {
    pendingWishlistItem = product;
    openAuthModal();
    return;
  }
  const items = getWishlist();
  const idx = items.findIndex(i => i.name === product.name);
  if (idx >= 0) {
    items.splice(idx, 1);
  } else {
    items.push({ name: product.name, price: product.price, image_url: product.image_url });
  }
  saveWishlist(items);
  toast.textContent = idx >= 0 ? `${product.name} removed from wishlist` : `${product.name} added to wishlist`;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}

function openProductPopup(product) {
  currentProduct = product;
  trackProductView(product.name);
  currentImageIndex = 0;
  const quantityOutput = document.getElementById('product-quantity');
  if (quantityOutput) quantityOutput.value = '1';
  if (quantityOutput) quantityOutput.textContent = '1';
  productName.textContent = product.name;
  productPrice.innerHTML = `${priceMarkup(product.price, product.discounted_price)}${Number(product.discounted_price) < Number(product.price) ? '<span class="discount-label">Discounted</span>' : ''}`;
  productDesc.textContent = product.details || 'Handcrafted with care. A timeless piece from our collection.';

  const sizes = ['S', 'M', 'L', 'XL', 'XXL'];
  const availableSizes = product.available_sizes || [];
  productSizes.innerHTML = sizes.map(s => `<button class="size-option${availableSizes.includes(s) ? '' : ' unavailable'}" data-size="${s}" ${availableSizes.includes(s) ? '' : 'disabled'}>${s}</button>`).join('');
  productSizes.querySelectorAll('.size-option').forEach(btn => {
    btn.addEventListener('click', () => {
      productSizes.querySelectorAll('.size-option').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    });
  });

  const productImage = imageFor(product.image_url, 0, product.name);
  const images = product.image_variants?.length ? product.image_variants : productImageVariants(productImage);
  productMainImage.innerHTML = `<img src="${images[0]}" alt="${escapeHtml(product.name)}">`;
  productThumbnails.innerHTML = images.map((img, i) => `
    <button class="thumb ${i === 0 ? 'active' : ''}" data-index="${i}">
      <img src="${img}" alt="View ${i + 1}" loading="lazy">
    </button>
  `).join('');
  productImageStack.innerHTML = images.map((img, i) => `
    <img class="product-stack-image" src="${img}" alt="${escapeHtml(product.name)} image ${i + 1}" loading="lazy">
  `).join('');

  const selectProductImage = (imageControl) => {
      currentImageIndex = Number(imageControl.dataset.index);
      productMainImage.innerHTML = `<img src="${images[currentImageIndex]}" alt="${escapeHtml(product.name)}">`;
      productThumbnails.querySelectorAll('.thumb').forEach(t => t.classList.remove('active'));
      productThumbnails.querySelector(`.thumb[data-index="${currentImageIndex}"]`)?.classList.add('active');
      imageControl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  };
  productThumbnails.querySelectorAll('.thumb').forEach(thumb => thumb.addEventListener('click', () => selectProductImage(thumb)));

  productAddToBag.onclick = () => {
    const selectedSize = productSizes.querySelector('.size-option.selected');
    if (!selectedSize) {
      toast.textContent = 'Please select a size';
      toast.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
      return;
    }
    const quantity = Math.max(1, Number(document.getElementById('product-quantity')?.textContent || 1));
    addToBag(product.name, discountedPrice(product.price, product.discounted_price), selectedSize.dataset.size, product.image_url, quantity);
    closeProductPopup();
  };

  productWishlistBtn.onclick = () => toggleWishlist(product);
  updateWishlistUI();

  productOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

const productQuantity = document.getElementById('product-quantity');
const productQuantityDecrease = document.getElementById('product-quantity-decrease');
const productQuantityIncrease = document.getElementById('product-quantity-increase');
function updateProductQuantity(delta) {
  if (!productQuantity) return;
  const next = Math.max(1, Number(productQuantity.textContent || 1) + delta);
  productQuantity.textContent = String(next);
}
if (productQuantityDecrease) productQuantityDecrease.addEventListener('click', () => updateProductQuantity(-1));
if (productQuantityIncrease) productQuantityIncrease.addEventListener('click', () => updateProductQuantity(1));

function closeProductPopup() {
  if (productOverlay) productOverlay.classList.remove('open');
  document.body.style.overflow = '';
  currentProduct = null;
}

function renderProducts(products) {
  console.log('renderProducts called, products:', products.length);
  if (!grid) return;
  if (!products.length) {
    grid.innerHTML = '<p class="empty-shop">Our next edit is being prepared. Please return soon.</p>';
    return;
  }
  grid.innerHTML = products.map((product, index) => {
    const details = [product.color, product.category].filter(Boolean).join(' · ') || 'Made with care';
    const action = `<button data-item="${escapeHtml(product.name)}" data-price="${discountedPrice(product.price, product.discounted_price)}">Add to bag</button>`;
    const tag = product.in_stock ? '' : '<span class="tag">Sold out</span>';
    const availableSizes = product.available_sizes || [];
    const sizeOptions = ['S', 'M', 'L', 'XL', 'XXL'].map(s => `<button class="size-option${availableSizes.includes(s) ? '' : ' unavailable'}" data-size="${s}" ${availableSizes.includes(s) ? '' : 'disabled'}>${s}</button>`).join('');
    return `<article class="product reveal"><div class="product-image reveal"><img src="${escapeHtml(imageFor(product.image_url, index, product.name))}" alt="${escapeHtml(product.name)}" loading="lazy">${tag}</div><div class="product-info"><div><h3>${escapeHtml(product.name)}</h3><p>${escapeHtml(details)}</p><div class="product-card-sizes">${sizeOptions}</div><button class="size-guide-btn" data-item="${escapeHtml(product.name)}">Size Guide</button></div><div class="buy"><span class="product-card-price">${priceMarkup(product.price, product.discounted_price)}</span>${action}</div></div></article>`;
  }).join('');
  observeReveals();
  setupImageHoverSlides();
}

function setupImageHoverSlides() {
  document.querySelectorAll('.collection-card img, .product-image img').forEach(image => {
    if (image.dataset.hoverSlidesReady === 'true') return;
    availableImageVariants(image.currentSrc || image.src).then(variants => {
      if (variants.length < 2) return;
      image.dataset.hoverSlidesReady = 'true';
      let index = 0;
      let timer = null;
      const stop = () => {
        clearInterval(timer);
        timer = null;
        index = 0;
        image.src = variants[0];
      };
      image.closest('.collection-card, .product-image')?.addEventListener('mouseenter', () => {
        clearInterval(timer);
        timer = setInterval(() => {
          index = (index + 1) % variants.length;
          image.src = variants[index];
        }, 1000);
      });
      image.closest('.collection-card, .product-image')?.addEventListener('mouseleave', stop);
    });
  });
}
window.setupImageHoverSlides = setupImageHoverSlides;

function sortProducts(products, sort) {
  const sorted = [...products];
  const views = viewCounts();
  if (sort === 'price-low') return sorted.sort((a, b) => Number(a.price) - Number(b.price));
  if (sort === 'price-high') return sorted.sort((a, b) => Number(b.price) - Number(a.price));
  if (sort === 'views') return sorted.sort((a, b) => (Number(views[b.name]) || 0) - (Number(views[a.name]) || 0));
  if (sort === 'discounts') return sorted.sort((a, b) => Number(b.price) - Number(a.price));
  return sorted;
}

function renderNewLaunches(products) {
  if (!newLaunchesTrack) return;

  const launches = products;

  const renderLaunchSet = (setIndex) => `
    <div class="new-launch-set">
      ${launches.map((product, index) => `
        <button class="new-launch-card" type="button" data-product-index="${index}" data-set-index="${setIndex}">
          <span class="new-launch-image"><img src="${escapeHtml(imageFor(product.image_url, index, product.name))}" alt="${escapeHtml(product.name)}" loading="lazy"></span>
          <span class="new-launch-copy"><strong>${escapeHtml(product.name)}</strong><small>${rupees(product.price)}</small></span>
        </button>
      `).join('')}
    </div>
  `;

  newLaunchesTrack.innerHTML = `${renderLaunchSet(0)}${renderLaunchSet(1)}`;

  // ← Add this: sync both sets to have identical width
  setTimeout(() => {
    const sets = newLaunchesTrack.querySelectorAll('.new-launch-set');
    if (sets.length >= 2) {
      const set1Width = sets[0].offsetWidth;
      const set2Width = sets[1].offsetWidth;
      const maxWidth = Math.max(set1Width, set2Width);

      sets.forEach(set => {
        set.style.minWidth = maxWidth + 'px';
        set.style.width = maxWidth + 'px';
      });
    }
  }, 100);

  newLaunchesTrack.querySelectorAll('.new-launch-card').forEach(card => {
    card.addEventListener('click', () => {
      const product = launches[Number(card.dataset.productIndex)];
      if (product) openProductPopup(product);
    });
  });
}

async function loadCatalog(retries = 3) {
  if (!grid) return;
  try {
    const response = await fetch('/api/store/products');
    if (!response.ok) throw new Error('Catalog unavailable');
    const { products } = await response.json();
    searchProducts = products || [];
    renderProducts(products);
    renderNewLaunches(products);
  } catch (error) {
    if (retries > 0) {
      await new Promise(r => setTimeout(r, 1000));
      return loadCatalog(retries - 1);
    }
    console.error('Failed to load catalog after retries:', error);
  }
}

function handleProductCardClick(event) {
    const productImage = event.target.closest('.product-image');
    const productName = event.target.closest('.product-info h3');
    const sizeBtn = event.target.closest('.size-guide-btn');
    const addBtn = event.target.closest('.buy button[data-item]');
    const sizeOption = event.target.closest('.product-card-sizes .size-option');

    if (sizeOption) {
      const card = sizeOption.closest('.product');
      card.querySelectorAll('.product-card-sizes .size-option').forEach(b => b.classList.remove('selected'));
      sizeOption.classList.add('selected');
      return;
    }
    if (sizeBtn) {
      const sizeGuideOverlay = document.getElementById('size-guide-overlay');
      if (sizeGuideOverlay) {
        sizeGuideOverlay.classList.add('open');
        document.body.style.overflow = 'hidden';
      }
      return;
    }
    if (addBtn) {
      const card = addBtn.closest('.product');
      const selectedSize = card.querySelector('.product-card-sizes .size-option.selected');
      if (!selectedSize) {
        toast.textContent = 'Please select a size';
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
        return;
      }
      const price = addBtn.dataset.price || 0;
      const cardImg = card.querySelector('.product-image img');
      const image_url = cardImg ? cardImg.src : '';
      addToBag(addBtn.dataset.item, price, selectedSize.dataset.size, image_url);
      return;
    }

    let product = null;
    if (productImage || productName) {
      const article = (productImage || productName).closest('.product');
      if (article) {
        const nameEl = article.querySelector('.product-info h3');
        const priceEl = article.querySelector('.buy strong');
        const imgEl = article.querySelector('.product-image img');
        const detailsEl = article.querySelector('.product-info p');
        const sizeButtons = article.querySelectorAll('.product-card-sizes .size-option:not(.unavailable)');
        const name = nameEl?.textContent?.trim() || '';
        const priceText = priceEl?.textContent?.trim() || '';
        const displayedPrice = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
        const image_url = imgEl?.src || '';
        const details = detailsEl?.textContent?.trim() || '';
        const availableSizes = Array.from(sizeButtons).map(btn => btn.dataset.size).filter(Boolean);
        product = searchProducts.find(item => item.name === name) || {
          name,
          price: Math.round(displayedPrice / 0.9),
          image_url,
          details,
          available_sizes: availableSizes
        };
      }
    }
    if (product) {
      openProductPopup(product);
    }
}

document.addEventListener('click', event => {
  if (!event.target.closest('.product')) return;
  handleProductCardClick(event);
});

if (cartItems) {
  cartItems.addEventListener('click', event => {
    const btn = event.target.closest('.cart-item-remove');
    if (!btn) return;
    removeFromBag(Number(btn.dataset.idx));
  });
}

if (checkoutBtn) {
  checkoutBtn.addEventListener('click', () => {
    if (bag.length) {
      closeCart();
      sessionStorage.removeItem('selected_address_id');
      setTimeout(() => { window.location.href = '/shop/shipping'; }, 350);
    }
  });
}
if (bagBtn) bagBtn.addEventListener('click', openCart);
if (cartClose) cartClose.addEventListener('click', closeCart);
if (cartOverlay) cartOverlay.addEventListener('click', closeCart);

const wishlistBtnHeader = document.querySelector('.wishlist-btn-header');
if (wishlistBtnHeader) wishlistBtnHeader.addEventListener('click', () => {
  if (!currentUser) {
    openAuthModal();
    return;
  }
  openWishlist();
});
if (wishlistClose) wishlistClose.addEventListener('click', closeWishlist);
if (wishlistOverlay) wishlistOverlay.addEventListener('click', closeWishlist);

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (cartSidebar && cartSidebar.classList.contains('open')) closeCart();
    if (productOverlay && productOverlay.classList.contains('open')) closeProductPopup();
    if (sizeGuideOverlay && sizeGuideOverlay.classList.contains('open')) closeSizeGuide();
    if (authOverlay && authOverlay.classList.contains('open')) closeAuthModal();
    if (wishlistSidebar && wishlistSidebar.classList.contains('open')) closeWishlist();
  }
});

const newsletterForm = document.querySelector('.newsletter form');
if (newsletterForm) {
  newsletterForm.addEventListener('submit', async event => {
    event.preventDefault();
    const emailInput = newsletterForm.querySelector('input[type="email"]');
    const email = emailInput.value.trim();
    if (!email) return;
    try {
      const res = await fetch('/api/newsletter/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (res.ok) {
        toast.textContent = 'You\'re on the list — thank you.';
      } else {
        toast.textContent = data.error || 'Subscription failed';
      }
    } catch {
      toast.textContent = 'Network error — please try again';
    }
    toast.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    newsletterForm.reset();
  });
}

if (productPopupClose) {
  productPopupClose.addEventListener('click', closeProductPopup);
}
if (productOverlay) {
  productOverlay.addEventListener('click', (e) => {
    if (e.target === productOverlay) closeProductPopup();
  });
}

const sizeGuideOverlay = document.getElementById('size-guide-overlay');
const sizeGuidePopup = document.getElementById('size-guide-popup');
const sizeGuideClose = document.getElementById('size-guide-close');
const sizeGuideLink = document.getElementById('size-guide-link');

function openSizeGuide() {
  if (sizeGuideOverlay) {
    sizeGuideOverlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}
function closeSizeGuide() {
  if (sizeGuideOverlay) {
    sizeGuideOverlay.classList.remove('open');
    document.body.style.overflow = '';
  }
}
if (sizeGuideLink) {
  sizeGuideLink.addEventListener('click', (e) => {
    e.preventDefault();
    openSizeGuide();
  });
}
if (sizeGuideClose) {
  sizeGuideClose.addEventListener('click', closeSizeGuide);
}
if (sizeGuideOverlay) {
  sizeGuideOverlay.addEventListener('click', (e) => {
    if (e.target === sizeGuideOverlay) closeSizeGuide();
  });
}

const parallax = document.querySelectorAll('.parallax');
function moveParallax(){ parallax.forEach(el => { const rect = el.parentElement.getBoundingClientRect(); const speed = Number(el.dataset.speed); el.style.transform = `translateY(${(rect.top + rect.height / 2) * speed}px)`; }); }
moveParallax(); window.addEventListener('scroll', moveParallax, {passive:true});

document.querySelectorAll('[data-before-after]').forEach(compare => {
  const range = compare.querySelector('.before-after-range');
  if (!range) return;
  const updateCompare = () => {
    compare.style.setProperty('--before-after-position', `${range.value}%`);
  };
  range.addEventListener('input', updateCompare);
  updateCompare();
});


function observeReveals() {
  const revealElements = document.querySelectorAll('.reveal:not(.visible)');
  console.log('observeReveals found', revealElements.length, 'elements');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -30px 0px' });
  document.querySelectorAll('.reveal:not(.visible)').forEach(el => {
    const rect = el.getBoundingClientRect();
    const inView = rect.top < window.innerHeight && rect.bottom > 0;
    if (inView) {
      el.classList.add('visible');
    } else {
      observer.observe(el);
    }
  });
}
observeReveals();
loadCart();

// Google Identity Services (GIS) Sign in with Google
// See: https://codelabs.developers.google.com/codelabs/sign-in-with-google-button
function handleGoogleCredentialResponse(response) {
  const credential = response.credential;
  fetch('/api/auth/google', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  })
    .then(res => res.json())
    .then(data => {
      if (data.user) {
        currentUser = data.user;
        updateAuthUI();
        closeAuthModal();
        toast.textContent = `Welcome, ${data.user.name}!`;
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
      } else if (data.error) {
        toast.textContent = data.error || 'Google sign-in failed';
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
      }
    })
    .catch(() => {
      toast.textContent = 'Network error during Google sign-in';
      toast.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    });
}

function initGoogleSignIn() {
  const gIdOnload = document.getElementById('g_id_onload');
  const gIdSignin = document.getElementById('google-button-container');
  if (!gIdOnload || !gIdSignin || !google) return;

  google.accounts.id.initialize({
    client_id: gIdOnload.getAttribute('data-client_id'),
    callback: handleGoogleCredentialResponse,
    auto_select: false,
    cancel_on_tap_outside: false,
  });

  google.accounts.id.renderButton(
    gIdSignin,
    { theme: 'outline', size: 'large', width: '100%', text: 'signin_with' },
    { type: 'standard' }
  );
}

// Initialize Google sign-in when the GIS library loads
if (typeof google !== 'undefined') {
  initGoogleSignIn();
} else {
  window.addEventListener('load', () => {
    const checkGoogle = setInterval(() => {
      if (typeof google !== 'undefined') {
        clearInterval(checkGoogle);
        initGoogleSignIn();
      }
    }, 100);
  });
}


// ---------------------------------------------------------------
// AUTHENTICATION
// ---------------------------------------------------------------
let currentUser = null;
const authBtn = document.getElementById('auth-btn');
const profileDropdown = document.getElementById('profile-dropdown');

const authOverlay = document.getElementById('auth-overlay');
const authClose = document.getElementById('auth-close');
const loginForm = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');
const loginError = document.getElementById('login-error');
const signupError = document.getElementById('signup-error');
const authIdentifierForm = document.getElementById('auth-identifier-form');
const authIdentifierInput = document.getElementById('auth-identifier');
const authStep1 = document.getElementById('auth-step-1');
const authStepSignup = document.getElementById('auth-step-signup');
const authStepLogin = document.getElementById('auth-step-login');
const authStepForgot = document.getElementById('auth-step-forgot');
const forgotPasswordLink = document.getElementById('forgot-password-link');
const forgotPasswordForm = document.getElementById('forgot-password-form');
const forgotError = document.getElementById('forgot-error');
let pendingIdentifier = '';

function showAuthStep(step) {
  [authStep1, authStepSignup, authStepLogin, authStepForgot].forEach(el => { if (el) el.style.display = 'none'; });
  if (step === 'identifier' && authStep1) authStep1.style.display = 'block';
  if (step === 'signup' && authStepSignup) authStepSignup.style.display = 'block';
  if (step === 'login' && authStepLogin) authStepLogin.style.display = 'block';
  if (step === 'forgot' && authStepForgot) authStepForgot.style.display = 'block';
}


async function updateAuthUI() {
  if (!authBtn) return;
  if (currentUser) {
    authBtn.textContent = currentUser.name.charAt(0).toUpperCase();
    authBtn.classList.add('logged-in');
    if (profileDropdown) {
      profileDropdown.innerHTML = `
        <div class="profile-header">
          <span class="profile-name">${escapeHtml(currentUser.name)}</span>
          <span class="profile-email">${escapeHtml(currentUser.email)}</span>
        </div>
        <div class="profile-links">
          <a href="/shop/shipping" class="profile-link">Shipping Address</a>
          <a href="/shop/shipping" class="profile-link">My Orders</a>
          <button class="profile-link" id="logout-btn">Logout</button>
        </div>
      `;
      const logoutBtn = document.getElementById('logout-btn');
      if (logoutBtn) logoutBtn.addEventListener('click', logout);
    }
  } else {
    authBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="6" r="4"></circle><path d="M4 21v-2a8 8 0 0 1 16 0v2"></path></svg>';
    authBtn.title = 'Account';
    authBtn.classList.remove('logged-in');
    if (profileDropdown) profileDropdown.classList.remove('open');
  }
  document.dispatchEvent(new Event('account-updated'));
}

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.user) {
      currentUser = data.user;
      updateAuthUI();
      await loadCartFromServer();
      await loadWishlistFromServer();
    } else {
      currentUser = null;
      updateAuthUI();
    }
  } catch {
    currentUser = null;
    updateAuthUI();
  }
}

if (authBtn) {
  authBtn.addEventListener('click', () => {
    if (currentUser) {
      profileDropdown.classList.toggle('open');
    } else {
      openAuthModal();
    }
  });
}
if (authClose) {
  authClose.addEventListener('click', closeAuthModal);
}
document.addEventListener('click', e => {
  if (!e.target.closest('.auth-menu')) {
    if (profileDropdown) profileDropdown.classList.remove('open');
  }
});

// ✅ FIXED: Check if elements exist before using them
function renderCheckout() {
  // Only run if we're on the checkout page (elements exist)
  const itemsEl = document.getElementById('checkout-items');
  const totalEl = document.getElementById('checkout-total');
  const placeBtn = document.getElementById('place-order-btn');

  if (!itemsEl || !totalEl || !placeBtn) {
    return; // Not on checkout page, exit early
  }

  loadCart();
  const countEl = document.getElementById('bag-count');

  const totalItems = bag.reduce((s, i) => s + i.qty, 0);
  if (countEl) countEl.textContent = totalItems;

  if (!bag.length) {
    itemsEl.innerHTML = '<p class="cart-empty" style="padding:40px 0;color:#7a6e62;font-family:var(--mono);font-size:13px">Your bag is empty.</p>';
    totalEl.textContent = '₹ 0';
    placeBtn.disabled = true;
    return;
  }

  placeBtn.disabled = false;
  const total = bag.reduce((s, i) => s + (i.price * i.qty), 0);
  totalEl.textContent = rupees(total);

  itemsEl.innerHTML = bag.map((item, idx) => `
    <div class="cart-item">
      <img src="${escapeHtml(imageFor(item.image_url, idx, item.name))}" alt="${escapeHtml(item.name)}" class="cart-item-image">
      <div class="cart-item-info">
        <p class="cart-item-name">${escapeHtml(item.name)}</p>
        <p class="cart-item-meta">Size: ${escapeHtml(item.size || 'M')} · ${rupees(item.price)} each</p>
        ${cartQuantityControls(item, idx)}
        <button class="cart-item-remove" data-idx="${idx}" onclick="removeFromBag(${idx}); renderCheckout();">Remove</button>
      </div>
      <strong>${rupees(item.price * item.qty)}</strong>
    </div>
  `).join('');
}

async function loadCartFromServer() {
  if (!currentUser) return;
  try {
    const res = await fetch('/api/user/cart');
    const data = await res.json();
    bag = mergeCartItems((data.cart || []).map(item => ({
      name: item.product_name,
      price: item.price,
      qty: item.qty,
      size: item.size || null,
      image_url: item.image_url || null
    })));
    updateCartUI();
    localStorage.setItem('tnt_cart', JSON.stringify(bag));
    syncCartToServer();
    if (typeof renderCheckout === 'function') renderCheckout();
  } catch {}
}

async function loadWishlistFromServer() {
  if (!currentUser) return;
  try {
    const res = await fetch('/api/user/wishlist');
    const data = await res.json();
    if (data.wishlist && data.wishlist.length) {
      const wishlist = data.wishlist.map(item => ({ name: item.product_name, price: item.price, image_url: item.image_url }));
      localStorage.setItem('tnt_wishlist', JSON.stringify(wishlist));
      updateWishlistUI();
    }
  } catch {}
}

function openAuthModal() {
  if (currentUser) {
    if (confirm(`Logout from ${currentUser.name}?`)) logout();
    return;
  }
  if (authOverlay) {
    authOverlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

function closeAuthModal() {
  if (authOverlay) {
    authOverlay.classList.remove('open');
    document.body.style.overflow = '';
  }
}



// ---------------------------------------------------------------
// ORDERS
// ---------------------------------------------------------------
function openOrders() {
  ordersOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
  loadOrders();
}

function closeOrders() {
  ordersOverlay.classList.remove('open');
  document.body.style.overflow = '';
}

// Orders functionality - requires orders modal HTML
// ordersClose.addEventListener('click', closeOrders);
// ordersOverlay.addEventListener('click', e => { if (e.target === ordersOverlay) closeOrders(); });

async function loadOrders() {
  if (!currentUser) {
    ordersList.innerHTML = '<p class="no-orders">Please login to view orders.</p>';
    return;
  }
  try {
    const res = await fetch('/api/orders');
    const data = await res.json();
    if (!data.orders || !data.orders.length) {
      ordersList.innerHTML = '<p class="no-orders">No orders yet.</p>';
      return;
    }
    const rupees = value => `₹ ${Number(value).toLocaleString('en-IN', {minimumFractionDigits: 0, maximumFractionDigits: 2})}`;
    ordersList.innerHTML = data.orders.map(order => {
      let items = [];
      try { items = JSON.parse(order.items); } catch {}
      const date = new Date(order.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
      const itemsList = items.map(i => `${i.name} × ${i.qty}`).join(', ');
      return `<div class="order-item">
        <div class="order-header">
          <span class="order-number">${order.order_number}</span>
          <span class="order-status ${order.status}">${order.status}</span>
        </div>
        <p class="order-date">${date}</p>
        <p class="order-items">${itemsList}</p>
        <p class="order-total">Total: ${rupees(order.total_amount)}</p>
      </div>`;
    }).join('');
  } catch {
    ordersList.innerHTML = '<p class="no-orders">Failed to load orders.</p>';
  }
}



if (authIdentifierForm) {
  authIdentifierForm.addEventListener('submit', async e => {
    e.preventDefault();
    const identifier = authIdentifierInput.value.trim();
    if (!identifier) return;
    try {
      const res = await fetch('/api/auth/check-user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier })
      });
      const data = await res.json();
      if (data.exists) {
        pendingIdentifier = identifier;
        showAuthStep('login');
        const loginPwd = document.getElementById('login-password');
        if (loginPwd) loginPwd.value = '';
        const loginErr = document.getElementById('login-error');
        if (loginErr) loginErr.textContent = '';
      } else {
        pendingIdentifier = identifier;
        const signupEmail = document.getElementById('signup-email');
        const signupPhone = document.getElementById('signup-phone');
        if (signupEmail) signupEmail.value = identifier.includes('@') ? identifier : '';
        if (signupPhone) signupPhone.value = identifier.includes('@') ? '' : identifier;
        showAuthStep('signup');
        const signupErr = document.getElementById('signup-error');
        if (signupErr) signupErr.textContent = '';
      }
    } catch {
      const errEl = document.getElementById('login-error');
      if (errEl) errEl.textContent = 'Network error. Try again.';
    }
  });
}

if (loginForm) {
  loginForm.addEventListener('submit', async e => {
    e.preventDefault();
    loginError.textContent = '';
    const password = document.getElementById('login-password').value;
    if (!pendingIdentifier || !password) return;
    try {
      const body = { password };
      if (pendingIdentifier.includes('@')) body.email = pendingIdentifier;
      else body.phone = pendingIdentifier;
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        loginError.textContent = data.error || 'Login failed';
        return;
      }
      currentUser = data.user;
      updateAuthUI();
      await loadCartFromServer();
      await loadWishlistFromServer();
      closeAuthModal();
      loginForm.reset();
      if (!pendingCartItem && !pendingWishlistItem && window.location.pathname.startsWith('/admin')) {
        window.location.reload();
        return;
      }
      if (pendingCartItem) {
        addToBag(pendingCartItem.name, pendingCartItem.price, pendingCartItem.size, pendingCartItem.image_url, pendingCartItem.quantity);
        pendingCartItem = null;
      } else if (pendingWishlistItem) {
        toggleWishlist(pendingWishlistItem);
        pendingWishlistItem = null;
      }
      toast.textContent = `Welcome back, ${currentUser.name}!`;
      toast.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    } catch {
      loginError.textContent = 'Network error. Try again.';
    }
  });
}

if (signupForm) {
  signupForm.addEventListener('submit', async e => {
    e.preventDefault();
    signupError.textContent = '';
    const name = document.getElementById('signup-name').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const phone = document.getElementById('signup-phone').value.trim();
    const password = document.getElementById('signup-password').value;
    if (!name || !email || !phone || !password) {
      signupError.textContent = 'All fields are required.';
      return;
    }
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, phone, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        signupError.textContent = data.error || 'Signup failed';
        return;
      }
      currentUser = data.user;
      updateAuthUI();
      closeAuthModal();
      signupForm.reset();
      if (!pendingCartItem && !pendingWishlistItem && window.location.pathname.startsWith('/admin')) {
        window.location.reload();
        return;
      }
      if (pendingCartItem) {
        addToBag(pendingCartItem.name, pendingCartItem.price, pendingCartItem.size, pendingCartItem.image_url, pendingCartItem.quantity);
        pendingCartItem = null;
      } else if (pendingWishlistItem) {
        toggleWishlist(pendingWishlistItem);
        pendingWishlistItem = null;
      }
      syncCartToServer();
      syncWishlistToServer();
      toast.textContent = `Welcome, ${currentUser.name}!`;
      toast.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    } catch {
      signupError.textContent = 'Network error. Try again.';
    }
  });
}

if (forgotPasswordLink) {
  forgotPasswordLink.addEventListener('click', e => {
    e.preventDefault();
    showAuthStep('forgot');
  });
}

if (forgotPasswordForm) {
  forgotPasswordForm.addEventListener('submit', async e => {
    e.preventDefault();
    forgotError.textContent = '';
    const email = document.getElementById('forgot-email').value.trim();
    if (!email) return;
    try {
      const res = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) {
        forgotError.textContent = data.error || 'Failed to send reset link';
        return;
      }
      forgotError.style.color = 'green';
      forgotError.textContent = 'Reset link sent! Check your email.';
      setTimeout(() => { showAuthStep('identifier'); forgotError.style.color = ''; }, 2000);
    } catch {
      forgotError.textContent = 'Network error. Try again.';
    }
  });
}

async function logout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  currentUser = null;
  bag = [];
  localStorage.removeItem('tnt_cart');
  localStorage.removeItem('tnt_wishlist');
  if (count) count.textContent = '0';
  if (wishlistCount) wishlistCount.textContent = '0';
  if (cartItems) cartItems.innerHTML = '<p class="cart-empty">Your bag is empty.</p>';
  if (cartTotal) cartTotal.textContent = '₹ 0';
  if (checkoutBtn) checkoutBtn.disabled = true;
  const checkoutItems = document.getElementById('checkout-items');
  if (checkoutItems) {
    checkoutItems.innerHTML = '<p class="cart-empty">Please login to add items in cart.</p>';
    const checkoutTotal = document.getElementById('checkout-total');
    const placeOrderBtn = document.getElementById('place-order-btn');
    if (checkoutTotal) checkoutTotal.textContent = '₹ 0';
    if (placeOrderBtn) placeOrderBtn.disabled = true;
  }
  if (authBtn) {
    authBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="6" r="4"></circle><path d="M4 21v-2a8 8 0 0 1 16 0v2"></path></svg>';
    authBtn.title = 'Account';
    authBtn.classList.remove('logged-in');
  }
  if (profileDropdown) profileDropdown.classList.remove('open');
  toast.textContent = 'Logged out';
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}

let cartSyncQueue = Promise.resolve();
function syncCartToServer() {
  if (!currentUser) return;
  const body = JSON.stringify({ cart: bag });
  cartSyncQueue = cartSyncQueue.catch(() => {}).then(() => fetch('/api/user/cart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    })).catch(() => {});
  return cartSyncQueue;
}

async function syncWishlistToServer() {
  if (!currentUser) return;
  const wishlist = getWishlist();
  try {
    await fetch('/api/user/wishlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wishlist }),
    });
  } catch {}
}

async function init() {
  console.log('init() called');
  document.querySelectorAll('img:not([loading])').forEach(image => {
    if (!image.closest('.site-header')) image.loading = 'lazy';
    image.decoding = 'async';
  });
  await checkAuth();
  updateWishlistUI();
  if (document.querySelector('.collection-section') || document.querySelector('.collections-page')) {
    loadCatalog();
  }
  if (!document.querySelector('.account-page') && typeof loadOrdersPage === 'function') {
    loadOrdersPage();
  }
  if (typeof renderCheckout === 'function') {
    renderCheckout();
  }
  if (document.body.dataset.showLogin === 'true' && !currentUser) {
    openAuthModal();
  }
  setupSearch();
  setupImageHoverSlides();
}

function setupSearch() {
  if (!searchBtn || !searchOverlay || !searchInput || !searchResults) return;

  const closeSearch = () => {
    searchOverlay.classList.remove('open');
    searchInput.value = '';
    searchResults.innerHTML = '';
  };

  searchBtn.addEventListener('click', () => {
    searchOverlay.classList.add('open');
    searchInput.focus();
  });

  searchInput.addEventListener('input', async (e) => {
    const query = e.target.value.trim().toLowerCase();
    if (!query) {
      searchResults.innerHTML = '';
      return;
    }

    try {
      if (!searchProducts.length) {
        const res = await fetch('/api/store/products');
        if (!res.ok) throw new Error('Catalog unavailable');
        const data = await res.json();
        searchProducts = data.products || [];
      }
      const products = searchProducts;

      const filtered = products.filter(p =>
        p.name.toLowerCase().includes(query) ||
        (p.category && p.category.toLowerCase().includes(query))
      );

      if (filtered.length === 0) {
        searchResults.innerHTML = '<p class="search-state">No products found</p>';
        return;
      }

      searchResults.innerHTML = filtered.slice(0, 8).map((p, index) => `
        <button class="search-result" type="button" data-product-index="${products.indexOf(p)}">
          <span class="search-result-image"><img src="${escapeHtml(imageFor(p.image_url, index, p.name))}" alt=""></span>
          <span class="search-result-copy">
            <strong>${escapeHtml(p.name)}</strong>
            <small>${escapeHtml([p.category, p.color].filter(Boolean).join(' · ') || 'Thugile & Threads')}</small>
          </span>
          <span class="search-result-arrow">↗</span>
        </button>
      `).join('');
    } catch {
      searchResults.innerHTML = '<p class="search-state">Search is unavailable right now.</p>';
    }
  });

  searchResults.addEventListener('click', event => {
    const result = event.target.closest('.search-result');
    if (!result) return;
    const product = searchProducts[Number(result.dataset.productIndex)];
    if (!product) return;
    closeSearch();
    if (productOverlay && productPopup) {
      openProductPopup(product);
    } else {
      window.location.href = `/shop/collections?product=${encodeURIComponent(product.name)}`;
    }
  });

  document.addEventListener('click', event => {
    const target = event.target;
    if (!searchOverlay.classList.contains('open') || !(target instanceof Element)) return;
    if (target.closest('.search-input, .search-results, .search-btn')) return;
    closeSearch();
  });

  // Close search when clicking outside
  searchOverlay.addEventListener('click', (e) => {
    if (e.target === searchOverlay) {
      searchOverlay.classList.remove('open');
      closeSearch();
    }
  });

  // Close on escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && searchOverlay.classList.contains('open')) {
      searchOverlay.classList.remove('open');
      closeSearch();
    }
  });
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

window.addEventListener('pageshow', () => {
  loadCart();
  updateWishlistUI();
  if (typeof renderCheckout === 'function') {
    renderCheckout();
  }
});
