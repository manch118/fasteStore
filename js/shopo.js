/* eslint-disable no-unused-vars */
let cart = [];
let currentPage = 1;
let currentSearchQuery = null;
const limit = 9;

function showNotification(message, isSuccess) {
    const notification = document.getElementById('notification');
    const notificationMessage = document.getElementById('notification-message');
    if (!notification || !notificationMessage) {
        console.error('Notification elements not found');
        return;
    }
    notificationMessage.textContent = message;
    notification.className = isSuccess ? 'success' : 'error';
    notification.style.display = 'block';
    setTimeout(() => notification.classList.add('show'), 10);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.style.display = 'none', 300);
    }, 3000);
}

function saveCartToSession() {
    sessionStorage.setItem('cart', JSON.stringify(cart));
}

function loadCartFromSession() {
    return JSON.parse(sessionStorage.getItem('cart') || '[]');
}

function saveCartToLocal() {
    localStorage.setItem('cart', JSON.stringify(cart));
}

function loadCartFromLocal() {
    return JSON.parse(localStorage.getItem('cart') || '[]');
}

function updateCartUI() {
    const cartItemsContainer = document.getElementById('cart-items');
    const cartEmpty = document.getElementById('cart-empty');
    const cartTotal = document.getElementById('cart-total');
    const cartCount = document.getElementById('cart-count');
    const checkoutBtn = document.querySelector('.checkout-btn');
    if (checkoutBtn) {
    checkoutBtn.addEventListener('click', async () => {
        try {
            // Проверяем аутентификацию
            const userResponse = await fetch('/api/me', { credentials: 'include' });
            const userData = await userResponse.json();
            if (!userData.success) {
                showNotification('Please log in to checkout', false);
                return;
            }

            // Создаём PayPal order
            const response = await fetch('/api/create-paypal-order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include'
            });
            const result = await response.json();
            if (result.success) {
                window.location.href = result.approval_url;  // Редирект на PayPal
            } else {
                showNotification('Error creating order: ' + (result.error || 'Unknown'), false);
            }
        } catch (error) {
            console.error('Checkout error:', error);
            showNotification('Checkout failed: ' + error.message, false);
        }
    });
}

    if (!cartItemsContainer || !cartEmpty || !cartTotal || !cartCount || !checkoutBtn) {
        console.error('Cart UI elements not found');
        return;
    }

    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    cartCount.textContent = totalItems;
    cartCount.classList.toggle('hidden', totalItems === 0);

    if (totalItems > 0) {
        cartCount.classList.add('updated');
        setTimeout(() => cartCount.classList.remove('updated'), 200);
    }

    if (cart.length === 0) {
        cartItemsContainer.innerHTML = '';
        cartItemsContainer.style.display = 'none';
        cartEmpty.style.display = 'flex';
        cartTotal.style.display = 'none';
        checkoutBtn.style.display = 'none';
        return;
    }

    cartItemsContainer.style.display = 'block';
    cartEmpty.style.display = 'none';
    cartTotal.style.display = 'block';
    checkoutBtn.style.display = 'block';

    cartItemsContainer.innerHTML = '';
    let total = 0;

    cart.forEach(item => {
        total += item.price * item.quantity;
        const cartItem = document.createElement('div');
        cartItem.className = 'cart-item';
        cartItem.innerHTML = `
            <img src="${item.image}" alt="${item.name}" loading="lazy" decoding="async">
            <div class="cart-item-details">
                <p class="name">${item.name}</p>
                <p class="price">$${item.price.toFixed(2)}</p>
            </div>
            <div class="cart-item-quantity">
                <button class="decrease" data-id="${item.product_id}">-</button>
                <input type="number" value="${item.quantity}" min="1" data-id="${item.product_id}" readonly>
                <button class="increase" data-id="${item.product_id}">+</button>
                <button class="remove" data-id="${item.product_id}">Remove</button>
            </div>
        `;
        cartItemsContainer.appendChild(cartItem);
    });

    cartTotal.textContent = `Total: $${total.toFixed(2)}`;

    document.querySelectorAll('.cart-item-quantity .decrease').forEach(button => {
        button.addEventListener('click', () => updateQuantity(button.dataset.id, -1), { passive: true });
    });

    document.querySelectorAll('.cart-item-quantity .increase').forEach(button => {
        button.addEventListener('click', () => updateQuantity(button.dataset.id, 1), { passive: true });
    });

    document.querySelectorAll('.cart-item-quantity .remove').forEach(button => {
        button.addEventListener('click', () => removeFromCart(button.dataset.id), { passive: true });
    });
}

async function fetchServerCart() {
    try {
        console.log('Fetching server cart from /api/cart');
        const response = await fetch('/api/cart', {
            method: 'GET',
            credentials: 'include'
        });
        console.log('fetchServerCart status:', response.status);
        console.log('fetchServerCart headers:', [...response.headers]);
        const text = await response.text();
        console.log('fetchServerCart response text:', text);
        let result;
        try {
            result = JSON.parse(text);
        } catch (e) {
            console.error('fetchServerCart JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('fetchServerCart result:', result);
        if (result.success && result.data) {
            cart = result.data;
            saveCartToLocal();
            updateCartUI();
            return true;
        } else {
            console.error('fetchServerCart failed:', result.error || 'No data');
            return false;
        }
    } catch (error) {
        console.error('fetchServerCart error:', error.message);
        showNotification('Error loading cart from server: ' + error.message, false);
        return false;
    }
}

async function loadCart() {
    try {
        console.log('Fetching user data from /api/me for loadCart');
        const response = await fetch('/api/me', {
            credentials: 'include'
        });
        console.log('loadCart /api/me status:', response.status);
        console.log('loadCart /api/me headers:', [...response.headers]);
        const text = await response.text();
        console.log('loadCart /api/me response text:', text);
        let userData;
        try {
            userData = JSON.parse(text);
        } catch (e) {
            console.error('loadCart JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('loadCart /api/me result:', userData);

        if (userData.success) {
            const success = await fetchServerCart();
            if (!success) {
                cart = loadCartFromLocal();
                updateCartUI();
            }
        } else {
            console.log('loadCart: User not authenticated, using session cart');
            cart = loadCartFromSession();
            updateCartUI();
        }
    } catch (error) {
        console.error('loadCart error:', error.message);
        cart = loadCartFromSession();
        updateCartUI();
    }
}

async function addToCart(product) {
    if (!product.id || !product.name || !product.price || !product.image) {
        console.error('addToCart: Invalid product data', product);
        showNotification('Error: Invalid product data', false);
        return;
    }

    const cartItem = {
        product_id: product.id,
        name: product.name,
        price: parseFloat(product.price),
        image: product.image,
        quantity: product.quantity || 1
    };

    try {
        console.log('Checking user with /api/me for addToCart');
        const userResponse = await fetch('/api/me', {
            credentials: 'include'
        });
        console.log('addToCart /api/me status:', userResponse.status);
        console.log('addToCart /api/me headers:', [...userResponse.headers]);
        const userText = await userResponse.text();
        console.log('addToCart /api/me response text:', userText);
        let userData;
        try {
            userData = JSON.parse(userText);
        } catch (e) {
            console.error('addToCart JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('addToCart /api/me result:', userData);

        if (!userData.success) {
            const existingItem = cart.find(item => item.product_id === product.id);
            if (existingItem) {
                existingItem.quantity += cartItem.quantity;
            } else {
                cart.push(cartItem);
            }
            saveCartToSession();
            updateCartUI();
            showNotification(`${product.name} added to cart!`, true);
            return;
        }

        console.log('Adding to server cart at /api/cart');
        const response = await fetch('/api/cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(cartItem)
        });
        console.log('addToCart status:', response.status);
        console.log('addToCart headers:', [...response.headers]);
        const text = await response.text();
        console.log('addToCart response text:', text);
        let result;
        try {
            result = JSON.parse(text);
        } catch (e) {
            console.error('addToCart JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('addToCart result:', result);

        if (result.success && result.data) {
            cart = result.data;
            saveCartToLocal();
            updateCartUI();
            showNotification(`${product.name} added to cart!`, true);
        } else {
            console.error('addToCart failed:', result.error || 'No data');
            showNotification('Error adding product to cart: ' + (result.error || 'Unknown error'), false);
        }
    } catch (error) {
        console.error('addToCart error:', error.message);
        showNotification('Error syncing with server: ' + error.message, false);
        const existingItem = cart.find(item => item.product_id === product.id);
        if (existingItem) {
            existingItem.quantity += cartItem.quantity;
        } else {
            cart.push(cartItem);
        }
        saveCartToLocal();
        updateCartUI();
    }
}

async function updateQuantity(productId, change, isDirect = false) {
    const item = cart.find(item => item.product_id === productId);
    if (!item) return;

    const newQuantity = isDirect ? change : item.quantity + change;
    if (newQuantity < 1) {
        removeFromCart(productId);
        return;
    }

    item.quantity = newQuantity;
    try {
        console.log('Checking user with /api/me for updateQuantity');
        const userResponse = await fetch('/api/me', {
            credentials: 'include'
        });
        console.log('updateQuantity /api/me status:', userResponse.status);
        console.log('updateQuantity /api/me headers:', [...userResponse.headers]);
        const userText = await userResponse.text();
        console.log('updateQuantity /api/me response text:', userText);
        let userData;
        try {
            userData = JSON.parse(userText);
        } catch (e) {
            console.error('updateQuantity JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('updateQuantity /api/me result:', userData);

        if (userData.success) saveCartToLocal();
        else saveCartToSession();

        updateCartUI();

        if (userData.success) {
            console.log(`Updating quantity for product ${productId} to ${newQuantity}`);
            const response = await fetch(`/api/cart/${productId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ quantity: newQuantity })
            });
            console.log('updateQuantity status:', response.status);
            console.log('updateQuantity headers:', [...response.headers]);
            const text = await response.text();
            console.log('updateQuantity response text:', text);
            let result;
            try {
                result = JSON.parse(text);
            } catch (e) {
                console.error('updateQuantity JSON parse error:', e);
                throw new Error('Invalid JSON response');
            }
            console.log('updateQuantity result:', result);

            if (result.success && result.data) {
                cart = result.data;
                saveCartToLocal();
                updateCartUI();
            } else {
                console.error('updateQuantity failed:', result.error || 'No data');
                showNotification('Error updating quantity: ' + (result.error || 'Unknown error'), false);
            }
        }
    } catch (error) {
        console.error('updateQuantity error:', error.message);
        showNotification('Error syncing with server: ' + error.message, false);
    }
}

async function removeFromCart(productId) {
    cart = cart.filter(item => item.product_id !== productId);
    try {
        console.log('Checking user with /api/me for removeFromCart');
        const userResponse = await fetch('/api/me', {
            credentials: 'include'
        });
        console.log('removeFromCart /api/me status:', userResponse.status);
        console.log('removeFromCart /api/me headers:', [...userResponse.headers]);
        const userText = await userResponse.text();
        console.log('removeFromCart /api/me response text:', userText);
        let userData;
        try {
            userData = JSON.parse(userText);
        } catch (e) {
            console.error('removeFromCart JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('removeFromCart /api/me result:', userData);

        if (userData.success) saveCartToLocal();
        else saveCartToSession();

        updateCartUI();
        showNotification('Item removed from cart', true);

        if (userData.success) {
            console.log(`Removing product ${productId} from server cart`);
            const response = await fetch(`/api/cart/${productId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include'
            });
            console.log('removeFromCart status:', response.status);
            console.log('removeFromCart headers:', [...response.headers]);
            const text = await response.text();
            console.log('removeFromCart response text:', text);
            let result;
            try {
                result = JSON.parse(text);
            } catch (e) {
                console.error('removeFromCart JSON parse error:', e);
                throw new Error('Invalid JSON response');
            }
            console.log('removeFromCart result:', result);

            if (result.success && result.data) {
                cart = result.data;
                saveCartToLocal();
                updateCartUI();
            } else {
                console.error('removeFromCart failed:', result.error || 'No data');
                showNotification('Error removing item: ' + (result.error || 'Unknown error'), false);
            }
        }
    } catch (error) {
        console.error('removeFromCart error:', error.message);
        showNotification('Error syncing with server: ' + error.message, false);
    }
}

async function loadNewArrivals() {
    console.log('Starting loadNewArrivals');
    try {
        const response = await fetch('/api/new-arrivals', {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        console.log('loadNewArrivals status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const text = await response.text();
        console.log('loadNewArrivals response text:', text);
        let data;
        try {
            data = JSON.parse(text);
        } catch (e) {
            console.error('loadNewArrivals JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('loadNewArrivals parsed data:', data);

        const grid = document.getElementById('new-arrivals-grid');
        if (!grid) {
            console.error('New arrivals grid not found');
            return;
        }

        console.log('Clearing new-arrivals-grid');
        grid.innerHTML = '';

        if (!Array.isArray(data) || data.length === 0) {
            console.log('No new arrivals found');
            grid.innerHTML = '<p class="fs-montserrat">No new arrivals found</p>';
            return;
        }

        console.log(`Rendering ${data.length} new arrivals`);
        data.forEach(product => {
            if (!product.id || !product.name || !product.price || !product.image) {
                console.warn('Invalid product data:', product);
                return;
            }
            const productDiv = document.createElement('div');
            productDiv.className = 'product-box';
            productDiv.innerHTML = `
                <img src="${product.image}" alt="${product.name}" loading="lazy" decoding="async" />
                <p class="product-name">${product.name}</p>
                <p class="price">$${parseFloat(product.price).toFixed(2)}</p>
                <div class="product-details">
                    <button class="add-to-cart" 
                            data-id="${product.id}" 
                            data-name="${product.name}" 
                            data-price="${product.price}" 
                            data-image="${product.image}">
                        <i class="uil uil-shopping-cart-alt"></i>
                    </button>
                    <i class="uil uil-heart-alt"></i>
                </div>
            `;
            grid.appendChild(productDiv);
        });

        console.log('Attaching event listeners to add-to-cart buttons');
        attachAddToCartListeners();
    } catch (error) {
        console.error('loadNewArrivals error:', error.message);
        showNotification('Failed to load new arrivals: ' + error.message, false);
        const grid = document.getElementById('new-arrivals-grid');
        if (grid) {
            grid.innerHTML = '<p class="fs-montserrat">Failed to load new arrivals</p>';
        }
    }
}

async function loadProducts(page = 1, sort = 'default', query = null) {
    try {
        let url = `/api/products?page=${page}&limit=${limit}&sort=${sort}`;
        if (query) url += `&search=${encodeURIComponent(query)}`;
        console.log('loadProducts fetching:', url);

        const response = await fetch(url);
        console.log('loadProducts status:', response.status);
        const text = await response.text();
        console.log('loadProducts response text:', text);
        let data;
        try {
            data = JSON.parse(text);
            console.log('loadProducts parsed data:', data);
        } catch (e) {
            console.error('loadProducts JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }

        if (!data.success) throw new Error(data.error || 'Failed to load products');

        const products = data.data;
        const totalItems = data.total || products.length;
        console.log('loadProducts totalItems:', totalItems, 'products:', products);

        const productContainer = document.getElementById('product-container');
        const productInfo = document.getElementById('product-info');
        if (productContainer) productContainer.innerHTML = '';

        if (products.length === 0) {
            if (productContainer) {
                productContainer.innerHTML = `<p class="fs-montserrat">No products found for "${query || ''}"</p>`;
            }
            if (productInfo) productInfo.querySelector('span').textContent = 'Showing 0-0 of 0 results';
        } else {
            products.forEach(product => {
                const productDiv = document.createElement('div');
                productDiv.classList.add('product-list', 'grid');
                productDiv.setAttribute('data-id', product.id);
                productDiv.setAttribute('data-category', product.category || '');
                productDiv.innerHTML = `
                    <img src="${product.image}" alt="${product.name}" />
                    <p class="fs-montserrat bold-600">${product.name}</p>
                    <p class="fs-montserrat">${product.category || 'Uncategorized'}</p>
                    <div class="shop-btn flex">
                        <button class="bg-red text-white fs-montserrat add-to-cart" 
                                data-id="${product.id}" 
                                data-name="${product.name}" 
                                data-price="${product.price}" 
                                data-image="${product.image}">Add To Cart</button>
                        <p class="fs-montserrat bold-700">$${product.price.toFixed(2)}</p>
                    </div>
                    ${product.category && ['Earphone', 'Gaming'].includes(product.category) ? '<div class="pup-up"><p class="fs-poppins">Sell</p></div>' : ''}
                `;

                // Делаем карточку кликабельной — открывает детальную страницу
                productDiv.style.cursor = 'pointer';
                productDiv.style.transition = 'transform 0.2s ease, box-shadow 0.2s ease';
                productDiv.addEventListener('mouseenter', () => {
                  productDiv.style.transform = 'translateY(-4px)';
                  productDiv.style.boxShadow = '0 8px 20px rgba(0,0,0,0.1)';
                }, { passive: true });
                productDiv.addEventListener('mouseleave', () => {
                  productDiv.style.transform = 'translateY(0)';
                  productDiv.style.boxShadow = '0 4px 8px rgba(0,0,0,0.05)';
                }, { passive: true });
                productDiv.addEventListener('click', (e) => {
                  // Проверяем, не кликнули ли на кнопку "Add to Cart" (чтобы не мешать)
                  if (!e.target.closest('.add-to-cart')) {
                    window.location.href = `product.html?id=${product.id}`;
                  }
                });

                if (productContainer) productContainer.appendChild(productDiv);
            });

            const start = (page - 1) * limit + 1;
            const end = Math.min(page * limit, totalItems);
            if (productInfo) productInfo.querySelector('span').textContent = `Showing ${start}-${end} of ${totalItems} results`;

            attachAddToCartListeners();
        }

        renderPagination(totalItems, page, limit);

    } catch (error) {
        console.error('loadProducts error:', error.message);
        const productContainer = document.getElementById('product-container');
        if (productContainer) productContainer.innerHTML = '<p class="fs-montserrat">Failed to load products. Please try again later.</p>';
    }
}

function renderPagination(totalItems, currentPage, limit) {
    const paginationControls = document.getElementById('pagination-controls');
    if (!paginationControls) return;
    paginationControls.innerHTML = '';
    const totalPages = Math.ceil(totalItems / limit);
    if (totalPages <= 1) return;

    if (currentPage > 1) {
        const prev = document.createElement('span');
        prev.innerHTML = '<i class="uil text-red uil-angle-double-left"></i>';
        prev.addEventListener('click', () => {
            currentPage = Math.max(1, currentPage - 1);
            loadProducts(currentPage, document.getElementById('sort-by')?.value || 'default', currentSearchQuery);
        });
        paginationControls.appendChild(prev);
    }

    for (let i = 1; i <= totalPages; i++) {
        const pageSpan = document.createElement('span');
        pageSpan.textContent = i;
        pageSpan.classList.add('bold-800');
        if (i === currentPage) {
            pageSpan.classList.add('bg-red', 'text-white', 'active');
        } else {
            pageSpan.classList.add('text-black');
            pageSpan.addEventListener('click', () => {
                currentPage = i;
                loadProducts(currentPage, document.getElementById('sort-by')?.value || 'default', currentSearchQuery);
            });
        }
        paginationControls.appendChild(pageSpan);
    }

    if (currentPage < totalPages) {
        const next = document.createElement('span');
        next.innerHTML = '<i class="uil text-red uil-angle-double-right"></i>';
        next.addEventListener('click', () => {
            currentPage = Math.min(totalPages, currentPage + 1);
            loadProducts(currentPage, document.getElementById('sort-by')?.value || 'default', currentSearchQuery);
        });
        paginationControls.appendChild(next);
    }
}

function attachAddToCartListeners() {
    document.querySelectorAll('.add-to-cart').forEach(button => {
        button.removeEventListener('click', handleAddToCart);
        button.addEventListener('click', handleAddToCart);
    });
}

function handleAddToCart(event) {
    const button = event.currentTarget;
    const product = {
        id: button.dataset.id,
        name: button.dataset.name,
        price: parseFloat(button.dataset.price),
        image: button.dataset.image,
        quantity: 1
    };
    console.log('Adding to cart:', product);
    addToCart(product);
}

function updateAuthState() {
    const authButtons = document.getElementById('auth-buttons');
    const userProfile = document.getElementById('user-profile');
    const userInitial = document.getElementById('user-initial');

    if (!authButtons || !userProfile || !userInitial) {
        console.error('Auth UI elements not found:', { authButtons, userProfile, userInitial });
        return;
    }

    console.log('Cookies in updateAuthState:', document.cookie);

    console.log('Fetching user data from /api/me for auth state');
    fetch('/api/me', {
        method: 'GET',
        credentials: 'include'
    })
    .then(response => {
        console.log('updateAuthState /api/me status:', response.status);
        console.log('updateAuthState /api/me headers:', [...response.headers]);
        return response.text().then(text => ({ text, response }));
    })
    .then(({ text, response }) => {
        console.log('updateAuthState /api/me response text:', text);
        let data;
        try {
            data = JSON.parse(text);
        } catch (e) {
            console.error('updateAuthState JSON parse error:', e);
            throw new Error('Invalid JSON response');
        }
        console.log('updateAuthState /api/me result:', data);
        if (data.success && data.user && data.user.username) {
            console.log('User authenticated, updating UI');
            authButtons.style.display = 'none';
            userProfile.style.display = 'flex';
            userInitial.textContent = data.user.username.charAt(0).toUpperCase();
            localStorage.setItem('username', data.user.username);
            loadCart();
        } else {
            console.log('User not authenticated, resetting UI');
            authButtons.style.display = 'flex';
            userProfile.style.display = 'none';
            userInitial.textContent = '';
            localStorage.removeItem('username');
            cart = loadCartFromSession();
            updateCartUI();
        }
        console.log('Current display state:', {
            authButtons: authButtons.style.display,
            userProfile: userProfile.style.display,
            userInitial: userInitial.textContent
        });
    })
    .catch(error => {
        console.error('updateAuthState error:', error.message);
        showNotification('Error checking auth state: ' + error.message, false);
        authButtons.style.display = 'flex';
        userProfile.style.display = 'none';
        userInitial.textContent = '';
        localStorage.removeItem('username');
        cart = loadCartFromSession();
        updateCartUI();
    });
}

function validateSignupForm(formData) {
    const username = formData.get('username')?.trim();
    const email = formData.get('email')?.trim();
    const password = formData.get('password');
    const confirmPassword = formData.get('confirm_password');

    if (!username || username.length < 3) {
        showNotification('Username must be at least 3 characters long', false);
        return false;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showNotification('Please enter a valid email', false);
        return false;
    }
    if (!password || password.length < 6) {
        showNotification('Password must be at least 6 characters long', false);
        return false;
    }
    if (password !== confirmPassword) {
        showNotification('Passwords do not match', false);
        return false;
    }
    return true;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const loginFormContainer = document.getElementById('login-form-container');
    const signupFormContainer = document.getElementById('signup-form-container');
    const cartContainer = document.getElementById('cart-icon');
    const loginToggle = document.getElementById('login-toggle');
    const signupToggle = document.getElementById('signup-toggle');
    const cartToggle = document.getElementById('cart-box');
    const switchToLogin = document.getElementById('switch-to-login');
    const crossBtn = document.getElementById('cross-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const cartOverlay = document.getElementById('cart-overlay');
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const sortSelect = document.getElementById('sort-by');

    console.log('DOM loaded, elements found:', {
        loginToggle, signupToggle, cartToggle, loginFormContainer,
        signupFormContainer, cartContainer, crossBtn, cartOverlay, logoutBtn
    });

    const closeAll = () => {
        if (loginFormContainer) loginFormContainer.style.display = 'none';
        if (signupFormContainer) signupFormContainer.style.display = 'none';
        if (cartContainer) cartContainer.classList.remove('open');
        if (cartOverlay) cartOverlay.classList.remove('visible');
    };

    if (loginToggle) {
        loginToggle.addEventListener('click', () => {
            console.log('Login toggle clicked');
            closeAll();
            if (loginFormContainer) loginFormContainer.style.display = 'block';
        });
    } else {
        console.error('Login toggle not found');
    }

    if (signupToggle) {
        signupToggle.addEventListener('click', () => {
            console.log('Signup toggle clicked');
            closeAll();
            if (signupFormContainer) signupFormContainer.style.display = 'block';
        });
    } else {
        console.error('Signup toggle not found');
    }

    if (switchToLogin) {
        switchToLogin.addEventListener('click', () => {
            console.log('Switch to login clicked');
            closeAll();
            if (loginFormContainer) loginFormContainer.style.display = 'block';
        });
    } else {
        console.error('Switch to login not found');
    }

    if (cartToggle) {
        cartToggle.addEventListener('click', () => {
            console.log('Cart toggle clicked');
            if (cartContainer) cartContainer.classList.add('open');
            if (cartOverlay) cartOverlay.classList.add('visible');
            loadCart();
        });
    } else {
        console.error('Cart toggle not found');
    }

    if (crossBtn) {
        crossBtn.addEventListener('click', () => {
            console.log('Cross button clicked');
            closeAll();
        });
    } else {
        console.error('Cross button not found');
    }

    if (cartOverlay) {
        cartOverlay.addEventListener('click', () => {
            console.log('Cart overlay clicked');
            closeAll();
        });
    } else {
        console.error('Cart overlay not found');
    }

    document.addEventListener('click', (event) => {
        const isClickInsideModal = (
            (loginFormContainer && loginFormContainer.contains(event.target)) ||
            (signupFormContainer && signupFormContainer.contains(event.target)) ||
            (cartContainer && cartContainer.contains(event.target))
        );
        const isClickOnToggleBtn = (
            event.target === loginToggle ||
            event.target === signupToggle ||
            event.target === cartToggle ||
            event.target === switchToLogin
        );
        const isClickOnUserProfile = event.target.closest('#user-profile');

        if (!isClickInsideModal && !isClickOnToggleBtn && !isClickOnUserProfile) {
            closeAll();
        }
    });

    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(loginForm);
            const username = formData.get('username').trim();
            const password = formData.get('password').trim();
            if (!username || !password) {
                showNotification('Please fill in all fields', false);
                return;
            }
            try {
                console.log('Sending login request to /login');
                const response = await fetch('/login', {
                    method: 'POST',
                    body: formData,
                    credentials: 'include'
                });
                console.log('Login status:', response.status);
                console.log('Login headers:', [...response.headers]);
                const text = await response.text();
                console.log('Login response text:', text);
                let result;
                try {
                    result = JSON.parse(text);
                } catch (e) {
                    console.error('Login JSON parse error:', e);
                    showNotification('Invalid server response', false);
                    return;
                }
                console.log('Login result:', result);
                if (result.success) {
                    console.log('Login successful, setting username and updating auth state');
                    localStorage.setItem('username', result.username);
                    updateAuthState();
                    closeAll();
                    showNotification('Login successful!', true);
                    loginForm.reset();
                } else {
                    showNotification(result.error || 'Login failed', false);
                }
            } catch (error) {
                console.error('Login error:', error.message);
                showNotification('Connection error: ' + error.message, false);
            }
        });
    } else {
        console.error('Login form not found');
    }

const signupForm = document.getElementById('signup-form');
if (signupForm) {
    signupForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(signupForm);
        if (!validateSignupForm(formData)) return;
        
        try {
            console.log('Sending signup request to /signup');
            const response = await fetch('/signup', {
                method: 'POST',
                body: formData,  // FormData, как в login
                credentials: 'include'
            });
            console.log('Signup status:', response.status);
            console.log('Signup headers:', [...response.headers]);
            const text = await response.text();
            console.log('Signup response text:', text);
            let result;
            try {
                result = JSON.parse(text);
            } catch (e) {
                console.error('Signup JSON parse error:', e);
                showNotification('Invalid server response', false);
                return;
            }
            console.log('Signup result:', result);
            
            if (response.ok && result.success) {
                console.log('Signup successful, setting username and updating auth state');
                localStorage.setItem('username', result.username);
                updateAuthState();
                closeAll();
                showNotification(result.message || 'Registration successful! You can now log in.', true);
                signupForm.reset();
            } else {
                const errorMsg = result.detail || result.error || 'Registration failed';
                showNotification(errorMsg, false);
            }
        } catch (error) {
            console.error('Signup error:', error.message);
            showNotification('Connection error: ' + error.message, false);
        }
    });
} else {
    console.error('Signup form not found');
}

    const subscribeForm = document.getElementById('subscribe-form');
    if (subscribeForm) {
        subscribeForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(subscribeForm);
            const email = formData.get('email').trim();
            if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showNotification('Please enter a valid email', false);
                return;
            }
            try {
                console.log('Sending subscribe request to /subscribe');
                const response = await fetch('/subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ email })
                });
                console.log('Subscribe status:', response.status);
                console.log('Subscribe headers:', [...response.headers]);
                const text = await response.text();
                console.log('Subscribe response text:', text);
                let result;
                try {
                    result = JSON.parse(text);
                } catch (e) {
                    console.error('Subscribe JSON parse error:', e);
                    throw new Error('Invalid JSON response');
                }
                console.log('Subscribe result:', result);
                if (result.success) {
                    showNotification('Subscription successful! Check your email for confirmation.', true);
                    subscribeForm.reset();
                } else {
                    showNotification(result.error || 'Subscription failed', false);
                }
            } catch (error) {
                console.error('Subscribe error:', error.message);
                showNotification('Connection error: ' + error.message, false);
            }
        });
    } else {
        console.error('Subscribe form not found');
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            console.log('Logout clicked');
            localStorage.removeItem('username');
            localStorage.removeItem('cart');
            sessionStorage.removeItem('cart');
            cart = [];
            updateAuthState();
            showNotification('Logged out! Cart cleared.', true);
            fetch('/admin/logout', {
                method: 'GET',
                credentials: 'include'
            }).then(response => {
                console.log('Logout status:', response.status);
                console.log('Logout headers:', [...response.headers]);
            }).catch(error => {
                console.error('Logout error:', error.message);
            });
        });
    } else {
        console.error('Logout button not found');
    }

    const productContainer = document.getElementById('product-container');
    if (productContainer) {
        const urlParams = new URLSearchParams(window.location.search);
        const initialSearchQuery = urlParams.get('search');
        if (initialSearchQuery) {
            currentSearchQuery = initialSearchQuery;
            if (searchInput) searchInput.value = initialSearchQuery;
        }

        const debouncedSearch = debounce((query) => {
            currentSearchQuery = query || null;
            currentPage = 1;
            loadProducts(currentPage, sortSelect ? sortSelect.value : 'default', currentSearchQuery);
        }, 300);

        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                debouncedSearch(e.target.value.trim());
            });
            searchInput.addEventListener('keypress', (event) => {
                if (event.key === 'Enter') {
                    debouncedSearch(searchInput.value.trim());
                }
            });
        } else {
            console.error('Search input not found');
        }

        if (searchButton) {
            searchButton.addEventListener('click', () => {
                debouncedSearch(searchInput.value.trim());
            });
        } else {
            console.error('Search button not found');
        }

        if (sortSelect) {
            sortSelect.addEventListener('change', () => {
                currentPage = 1;
                loadProducts(currentPage, sortSelect.value, currentSearchQuery);
            });
        } else {
            console.error('Sort select not found');
        }

        loadProducts(currentPage, sortSelect ? sortSelect.value : 'default', currentSearchQuery);
    } else {
        console.error('Product container not found');
    }

    updateAuthState();
    loadNewArrivals();
    loadCart();
});