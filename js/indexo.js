
// Navigation Bar

const navOpen = document.querySelector('.mobile-open-btn');
const navClose = document.querySelector('.mobile-close-btn');
const primaryNavigation = document.getElementById('primary-navigation');

if (navOpen && primaryNavigation) {
  navOpen.addEventListener('click', () => {
    const visibility = primaryNavigation.getAttribute('data-visible');
    const willOpen = visibility === 'false';
    primaryNavigation.setAttribute('data-visible', willOpen ? true : false);
    if (navClose) navClose.setAttribute('data-visible', willOpen ? true : false);
    if (typeof cartItme !== 'undefined' && cartItme) {
      cartItme.setAttribute('data-visible', false);
    }
    document.body.style.overflow = willOpen ? 'hidden' : '';
  }, { passive: true });
}

if (navClose && primaryNavigation) {
  navClose.addEventListener('click', () => {
    const visibility = primaryNavigation.getAttribute('data-visible');
    if (visibility === 'true') {
      primaryNavigation.setAttribute('data-visible', false);
      navClose.setAttribute('data-visible', false);
      document.body.style.overflow = '';
    }
  }, { passive: true });
}

// Auto-close mobile nav when a navigation link is tapped (prevents overlay blocking navigation)
if (primaryNavigation) {
  primaryNavigation.addEventListener('click', (e) => {
    const target = e.target;
    if (target && target.closest('a')) {
      primaryNavigation.setAttribute('data-visible', false);
      if (navClose) navClose.setAttribute('data-visible', false);
      document.body.style.overflow = '';
    }
  }, { passive: true });
}


// ===========================Cart Menu===================

const shoppingBtn = document.getElementById('cart-box');
const cartItme = document.getElementById('cart-icon');
const crossBtn = document.getElementById('cross-btn');

shoppingBtn.addEventListener('click', ()=>{
    const showCart = cartItme.getAttribute('data-visible');
   
    if(showCart === 'false'){
        cartItme.setAttribute('data-visible', true)
    }else{
        cartItme.setAttribute('data-visible', false)
    }
})

crossBtn.addEventListener('click', ()=>{
    const showCart = cartItme.getAttribute('data-visible');
   
    if(showCart === 'true'){
        cartItme.setAttribute('data-visible', false)
    }
})
// ====================== Login Form Toggle ======================

document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("login-toggle");
  const loginForm = document.getElementById("login-form-container");

  if (toggleBtn && loginForm) {
    toggleBtn.addEventListener("click", function (e) {
      e.stopPropagation(); // Чтобы клик не закрыл форму сразу
      const isVisible = loginForm.style.display === "block";
      loginForm.style.display = isVisible ? "none" : "block";
    });

    // Закрытие формы при клике вне её
    document.addEventListener("click", function (event) {
      if (!loginForm.contains(event.target) && event.target !== toggleBtn) {
        loginForm.style.display = "none";
      }
    });

    // Остановить всплытие при клике по форме
    loginForm.addEventListener("click", function (e) {
      e.stopPropagation();
    });
  }
});


// ====================== Login Form Toggle ======================

const toggleBtn = document.getElementById("login-toggle");
const loginForm = document.getElementById("login-form-container");

if (toggleBtn && loginForm) {
  toggleBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    const isVisible = loginForm.style.display === "block";
    loginForm.style.display = isVisible ? "none" : "block";
  });

  document.addEventListener("click", function (event) {
    if (!loginForm.contains(event.target) && event.target !== toggleBtn) {
      loginForm.style.display = "none";
    }
  });

  loginForm.addEventListener("click", function (e) {
    e.stopPropagation();
  });
} else {
  console.warn("Login toggle or form not found in DOM");
}

