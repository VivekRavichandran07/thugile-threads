const count = document.querySelector('#bag-count');
const wishlistCount = document.querySelector('#wishlist-count');
const toast = document.querySelector('#toast');
const grid = document.querySelector('.products');
const bagBtn = document.querySelector('#bag-btn');
const cartSidebar = document.querySelector('#cart-sidebar');
const cartOverlay = document.querySelector('#cart-overlay');
const cartClose = document.querySelector('#cart-close');
const cartItems = document.querySelector('#cart-items');
const cartTotal = document.querySelector('#cart-total');
const checkoutBtn = document.querySelector('#checkout-btn');
const floatingLogo = document.querySelector('.floating-logo');
const productOverlay = document.getElementById('product-overlay');
const productPopup = document.getElementById('product-popup');
const productPopupClose = document.getElementById('product-popup-close');
const productMainImage = document.getElementById('product-main-image');
const productThumbnails = document.getElementById('product-thumbnails');
const productName = document.getElementById('product-popup-name');
const productPrice = document.getElementById('product-popup-price');
const productDesc = document.getElementById('product-popup-desc');
const productSizes = document.getElementById('product-popup-sizes');
const productAddToBag = document.getElementById('product-add-to-bag');
const productWishlistBtn = document.getElementById('product-wishlist-btn');
const productSizeGuide = document.getElementById('product-size-guide');
const fallbackImages = [
  'https://images.pexels.com/photos/13155751/pexels-photo-13155751.jpeg?auto=format&fit=crop&w=1100&q=85',
  'https://images.pexels.com/photos/9419023/pexels-photo-9419023.jpeg?auto=format&fit=crop&w=900&q=85',
  'https://images.pexels.com/photos/37054322/pexels-photo-37054322.jpeg?auto=format&fit=crop&w=900&q=85',
  'https://images.pexels.com/photos/28428053/pexels-photo-28428053.jpeg?auto=format&fit=crop&w=900&q=85'
];
let bag = [], toastTimer, lastScrollY = 0, currentProduct = null, currentImageIndex = 0;
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
    'Kodi Silk Coord': '/static/storefront/assets/Chudidar/KodiSilkCoord.png',
    'Valli Rayon Kurta': '/static/storefront/assets/Chudidar/ValliRayonKurta.png',
    'Poonkodi Linen Set': '/static/storefront/assets/Chudidar/PoonkodiLinenSet.png',
    'Malli Cotton Kurta': '/static/storefront/assets/Chudidar/MalliCottonKurta.png',
    'Nila Daily Wear Kurti': '/static/storefront/assets/Chudidar/NilaDailyWearKurti.png',
    'Sindhu Business Co-ord': '/static/storefront/assets/Chudidar/SindhuBusinessCoord.png',
    'Pavithra Workwear Set': '/static/storefront/assets/Chudidar/PavithraWorkwearSet.png',
    'Mala Office Kurta': '/static/storefront/assets/Chudidar/MalaOfficeKurta.png',
    'Kaveri Executive Set': '/static/storefront/assets/Chudidar/KaveriExecutiveSet.png',
    'Mayil Set': '/static/storefront/assets/Chudidar/MayilSet.png',
    'Thamarai Set': '/static/storefront/assets/Chudidar/ThamaraiSet.png',
    'Vennila Set': '/static/storefront/assets/Chudidar/VennilaSet.png',
    'Manjal Set': '/static/storefront/assets/Chudidar/ManjalSet.png',
    'Maragatham Set': '/static/storefront/assets/Chudidar/MaragathamSet.png',
    'Rosa Set': '/static/storefront/assets/Chudidar/RosaSet.png',
    'Neelam Set': '/static/storefront/assets/Chudidar/NeelamSet.png',
    'Gulmohar Set': '/static/storefront/assets/Chudidar/GulmoharSet.png'
  };
  return imageMap[name] || (url && /^https?:\/\//i.test(url) ? url : fallbackImages[index % fallbackImages.length]);
};
const rupees = value => `₹ ${Number(value).toLocaleString('en-IN', {minimumFractionDigits: 0, maximumFractionDigits: 2})}`;

function loadCart() {
  try {
    const saved = localStorage.getItem('tnt_cart');
    bag = saved ? JSON.parse(saved) : [];
  } catch {
    bag = [];
  }
  updateCartUI();
}

function saveCart() {
  localStorage.setItem('tnt_cart', JSON.stringify(bag));
  updateCartUI();
  syncCartToServer();
}

function updateCartUI() {
  const totalItems = bag.reduce((sum, item) => sum + item.qty, 0);
  count.textContent = totalItems;
  renderCartItems();
}

function renderCartItems() {
  if (!bag.length) {
    cartItems.innerHTML = '<p class="cart-empty">Your bag is empty.</p>';
    cartTotal.textContent = '₹ 0';
    checkoutBtn.disabled = true;
    return;
  }
  checkoutBtn.disabled = false;
  const total = bag.reduce((sum, item) => sum + (item.price * item.qty), 0);
  cartTotal.textContent = rupees(total);
  cartItems.innerHTML = bag.map((item, idx) => `
    <div class="cart-item">
      <div class="cart-item-info">
        <p class="cart-item-name">${escapeHtml(item.name)}</p>
        <p class="cart-item-meta">Qty: ${item.qty} · ${rupees(item.price)} each</p>
        <button class="cart-item-remove" data-idx="${idx}">Remove</button>
      </div>
      <strong>${rupees(item.price * item.qty)}</strong>
    </div>
  `).join('');
}

function addToBag(name, price) {
  const existing = bag.find(item => item.name === name);
  if (existing) {
    existing.qty += 1;
  } else {
    bag.push({ name, price: Number(price), qty: 1 });
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
  cartSidebar.classList.add('open');
  cartOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeCart() {
  cartSidebar.classList.remove('open');
  cartOverlay.classList.remove('open');
  document.body.style.overflow = '';
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
  currentImageIndex = 0;
  productName.textContent = product.name;
  productPrice.textContent = rupees(product.price);
  productDesc.textContent = product.details || 'Handcrafted with care. A timeless piece from our collection.';
  
  const sizes = ['S', 'M', 'L', 'XL', 'XXL'];
  productSizes.innerHTML = sizes.map(s => `<button class="size-option" data-size="${s}">${s}</button>`).join('');
  productSizes.querySelectorAll('.size-option').forEach(btn => {
    btn.addEventListener('click', () => {
      productSizes.querySelectorAll('.size-option').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    });
  });
  
  const images = [
    product.image_url || fallbackImages[0],
    fallbackImages[1],
    fallbackImages[2],
    fallbackImages[3],
    fallbackImages[0]
  ];
  productMainImage.innerHTML = `<img src="${images[0]}" alt="${escapeHtml(product.name)}">`;
  productThumbnails.innerHTML = images.map((img, i) => `
    <button class="thumb ${i === 0 ? 'active' : ''}" data-index="${i}">
      <img src="${img}" alt="View ${i + 1}" loading="lazy">
    </button>
  `).join('');
  
  productThumbnails.querySelectorAll('.thumb').forEach(thumb => {
    thumb.addEventListener('click', () => {
      currentImageIndex = Number(thumb.dataset.index);
      productMainImage.innerHTML = `<img src="${images[currentImageIndex]}" alt="${escapeHtml(product.name)}">`;
      productThumbnails.querySelectorAll('.thumb').forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
    });
  });
  
  productAddToBag.onclick = () => {
    addToBag(product.name, product.price);
    closeProductPopup();
  };
  
  productWishlistBtn.onclick = () => toggleWishlist(product);
  updateWishlistUI();
  
  productOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeProductPopup() {
  productOverlay.classList.remove('open');
  document.body.style.overflow = '';
  currentProduct = null;
}

function renderProducts(products) {
  if (!products.length) {
    grid.innerHTML = '<p class="empty-shop">Our next edit is being prepared. Please return soon.</p>';
    return;
  }
  grid.innerHTML = products.map((product, index) => {
    const details = [product.color, product.category, product.size].filter(Boolean).join(' · ') || 'Made with care';
    const action = product.in_stock ? `<button data-item="${escapeHtml(product.name)}" data-price="${product.price || ''}">Add to bag</button>` : '<span class="sold-out">Sold out</span>';
    const tag = product.in_stock ? '' : '<span class="tag">Sold out</span>';
    return `<article class="product reveal"><div class="product-image reveal"><img src="${escapeHtml(imageFor(product.image_url, index, product.name))}" alt="${escapeHtml(product.name)}" loading="lazy">${tag}</div><div class="product-info"><div><h3>${escapeHtml(product.name)}</h3><p>${escapeHtml(details)}</p></div><div class="buy"><strong>${rupees(product.price)}</strong>${action}<button class="size-guide-btn" data-item="${escapeHtml(product.name)}">Size Guide</button></div></div></article>`;
  }).join('');
  observeReveals();
}

async function loadCatalog() {
  try {
    
    const response = await fetch('/api/store/products');
    
    if (!response.ok) throw new Error('Catalog unavailable');
    const { products } = await response.json();
    
    renderProducts(products);
  } catch (error) {
    
    grid.innerHTML = '<p class="empty-shop">The collection is temporarily unavailable. Please refresh and try again.</p>';
  }
}

grid.addEventListener('click', event => {
  const productImage = event.target.closest('.product-image');
  const productName = event.target.closest('.product-info h3');
  const sizeBtn = event.target.closest('.size-guide-btn');
  const addBtn = event.target.closest('.buy button[data-item]');

  if (sizeBtn) {
    const sizeGuideOverlay = document.getElementById('size-guide-overlay');
    if (sizeGuideOverlay) {
      sizeGuideOverlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
    return;
  }
  if (addBtn) {
    const price = addBtn.dataset.price || 0;
    addToBag(addBtn.dataset.item, price);
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
      const name = nameEl?.textContent?.trim() || '';
      const priceText = priceEl?.textContent?.trim() || '';
      const price = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
      const image_url = imgEl?.src || '';
      const details = detailsEl?.textContent?.trim() || '';
      product = { name, price, image_url, details };
    }
  }
  if (product) {
    openProductPopup(product);
  }
});

cartItems.addEventListener('click', event => {
  const btn = event.target.closest('.cart-item-remove');
  if (!btn) return;
  removeFromBag(Number(btn.dataset.idx));
});

checkoutBtn.addEventListener('click', () => {
  if (bag.length) {
    closeCart();
    setTimeout(() => { window.location.href = '/shop/checkout'; }, 350);
  }
});
bagBtn.addEventListener('click', openCart);
cartClose.addEventListener('click', closeCart);
cartOverlay.addEventListener('click', closeCart);
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeCart(); });

document.querySelector('.newsletter form').addEventListener('submit', event => {
  event.preventDefault(); event.currentTarget.reset();
  toast.textContent = 'You\'re on the list — thank you.'; toast.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
});

if (productPopupClose) {
  productPopupClose.addEventListener('click', closeProductPopup);
}
if (productOverlay) {
  productOverlay.addEventListener('click', (e) => {
    if (e.target === productOverlay) closeProductPopup();
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && productOverlay && productOverlay.classList.contains('open')) {
    closeProductPopup();
  }
});

const sizeGuideOverlay = document.getElementById('size-guide-overlay');
const sizeGuidePopup = document.getElementById('size-guide-popup');
const sizeGuideClose = document.getElementById('size-guide-close');
const sizeGuideLink = document.getElementById('size-guide-link');

function openSizeGuide() {
  sizeGuideOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeSizeGuide() {
  sizeGuideOverlay.classList.remove('open');
  document.body.style.overflow = '';
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
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && sizeGuideOverlay && sizeGuideOverlay.classList.contains('open')) {
    closeSizeGuide();
  }
});

if (productSizeGuide) {
  productSizeGuide.addEventListener('click', (e) => {
    e.preventDefault();
    openSizeGuide();
  });
}

const parallax = document.querySelectorAll('.parallax');
function moveParallax(){ parallax.forEach(el => { const rect = el.parentElement.getBoundingClientRect(); const speed = Number(el.dataset.speed); el.style.transform = `translateY(${(rect.top + rect.height / 2) * speed}px)`; }); }
moveParallax(); window.addEventListener('scroll', moveParallax, {passive:true});

function handleLogoScroll() {
  const currentY = window.scrollY;
  const header = document.querySelector('.site-header');
  if (currentY > 80) {
    floatingLogo.classList.add('logo-scrolled');
    header.classList.add('logo-scrolled');
  } else {
    floatingLogo.classList.remove('logo-scrolled');
    header.classList.remove('logo-scrolled');
  }
  lastScrollY = currentY;
}
window.addEventListener('scroll', handleLogoScroll, {passive:true});

function observeReveals() {
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
checkAuth();

// ---------------------------------------------------------------
// AUTHENTICATION
// ---------------------------------------------------------------
let currentUser = null;
const authBtn = document.getElementById('auth-btn');

const authOverlay = document.getElementById('auth-overlay');
const authClose = document.getElementById('auth-close');
const authTabs = document.querySelectorAll('.auth-tab');
const loginForm = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');
const loginError = document.getElementById('login-error');
const signupError = document.getElementById('signup-error');


async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.user) {
      currentUser = data.user;
      authBtn.textContent = '✓';
      authBtn.title = `Logged in as ${currentUser.name}`;
    } else {
      currentUser = null;
      authBtn.textContent = '👤';
      authBtn.title = 'Account';
    }
  } catch {
    currentUser = null;
  }
}

async function loadCartFromServer() {
  if (!currentUser) return;
  try {
    const res = await fetch('/api/user/cart');
    const data = await res.json();
    if (data.cart && data.cart.length) {
      bag = data.cart.map(item => ({ name: item.product_name, price: item.price, qty: item.qty }));
      updateCartUI();
      localStorage.setItem('tnt_cart', JSON.stringify(bag));
    }
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
  authOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeAuthModal() {
  authOverlay.classList.remove('open');
  document.body.style.overflow = '';
}

authBtn.addEventListener('click', openAuthModal);
authClose.addEventListener('click', closeAuthModal);
authOverlay.addEventListener('click', e => { if (e.target === authOverlay) closeAuthModal(); });

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

ordersClose.addEventListener('click', closeOrders);
ordersOverlay.addEventListener('click', e => { if (e.target === ordersOverlay) closeOrders(); });

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

authBtn.addEventListener('click', openAuthModal);
authClose.addEventListener('click', closeAuthModal);
authOverlay.addEventListener('click', e => { if (e.target === authOverlay) closeAuthModal(); });

authTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    authTabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    loginForm.classList.toggle('hidden', target !== 'login');
    signupForm.classList.toggle('hidden', target !== 'signup');
    loginError.textContent = '';
    signupError.textContent = '';
  });
});

loginForm.addEventListener('submit', async e => {
  e.preventDefault();
  loginError.textContent = '';
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      loginError.textContent = data.error || 'Login failed';
      return;
    }
    currentUser = data.user;
    authBtn.textContent = '✓';
    authBtn.title = `Logged in as ${currentUser.name}`;
    closeAuthModal();
    loginForm.reset();
    syncCartToServer();
    syncWishlistToServer();
    toast.textContent = `Welcome back, ${currentUser.name}!`;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
  } catch {
    loginError.textContent = 'Network error. Try again.';
  }
});

signupForm.addEventListener('submit', async e => {
  e.preventDefault();
  signupError.textContent = '';
  const name = document.getElementById('signup-name').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      signupError.textContent = data.error || 'Signup failed';
      return;
    }
    currentUser = data.user;
    authBtn.textContent = '✓';
    authBtn.title = `Logged in as ${currentUser.name}`;
    closeAuthModal();
    signupForm.reset();
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

async function logout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  currentUser = null;
  authBtn.textContent = '👤';
  authBtn.title = 'Account';
  toast.textContent = 'Logged out';
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}

async function syncCartToServer() {
  if (!currentUser) return;
  try {
    await fetch('/api/user/cart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cart: bag }),
    });
  } catch {}
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
  
  handleLogoScroll();
  updateWishlistUI();
  if (document.querySelector('.collection-section')) {
    
    loadCatalog();
  } else {
    
  }
  if (currentUser) {
    await loadCartFromServer();
    await loadWishlistFromServer();
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
