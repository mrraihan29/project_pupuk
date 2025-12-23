// Sidebar + nav interactions extracted from base template for reuse
(function () {
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.getElementById('mainContent');
  const overlay = document.getElementById('sidebarOverlay');

  function openSection(target, toggles, submenus) {
    submenus.forEach((menu) => {
      const btn = document.querySelector(`.nav-section-toggle[data-target="${menu.id}"]`);
      const shouldOpen = target && menu === target;
      menu.classList.toggle('show', shouldOpen);
      if (btn) {
        btn.setAttribute('aria-expanded', shouldOpen);
        btn.classList.toggle('open', shouldOpen);
      }
    });
  }

  function initSidebarDropdowns() {
    const toggles = document.querySelectorAll('.nav-section-toggle');
    const submenus = document.querySelectorAll('.submenu');
    const navLinks = document.querySelectorAll('.submenu .nav-link, .nav > .nav-link');

    toggles.forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.target);
        if (!target) return;
        const isOpen = target.classList.contains('show');

        if (isOpen) {
          target.classList.remove('show');
          btn.setAttribute('aria-expanded', 'false');
          btn.classList.remove('open');
        } else {
          openSection(target, toggles, submenus);
        }
      });
    });

    const activeLink = document.querySelector('.submenu .nav-link.active');
    const defaultOpen = activeLink ? activeLink.closest('.submenu') : submenus[0];
    if (defaultOpen) {
      openSection(defaultOpen, toggles, submenus);
    }

    navLinks.forEach((link) => {
      link.addEventListener('click', closeMobileSidebar);
    });
  }

  function toggleSidebar() {
    const isMobile = window.innerWidth <= 992;
    if (isMobile) {
      sidebar.classList.toggle('mobile-expanded');
      overlay.classList.toggle('active');
    } else {
      sidebar.classList.toggle('collapsed');
      mainContent.classList.toggle('collapsed');
    }
  }

  function closeMobileSidebar() {
    sidebar.classList.remove('mobile-expanded');
    overlay.classList.remove('active');
  }

  function handleResize() {
    const isMobile = window.innerWidth <= 992;

    if (isMobile) {
      sidebar.classList.remove('collapsed');
      mainContent.classList.remove('collapsed');
      if (!sidebar.classList.contains('mobile-expanded')) {
        overlay.classList.remove('active');
      }
    } else {
      sidebar.classList.remove('mobile-expanded');
      overlay.classList.remove('active');
    }
  }

  // Expose for inline onclick handlers
  window.toggleSidebar = toggleSidebar;
  window.closeMobileSidebar = closeMobileSidebar;

  window.addEventListener('resize', handleResize);
  document.addEventListener('DOMContentLoaded', initSidebarDropdowns);
})();
