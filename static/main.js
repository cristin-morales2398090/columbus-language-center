(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Revelado al hacer scroll (escalera de niveles, ruta del estudiante)
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: .25 });
  document.querySelectorAll('.reveal').forEach(el => reduce ? el.classList.add('in') : io.observe(el));
  // Contadores
  document.querySelectorAll('[data-count]').forEach(el => {
    if (reduce) return;
    const n = +el.dataset.count, suf = el.dataset.suffix || '';
    el.textContent = '0' + suf;
    const o = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      o.disconnect();
      const t0 = performance.now();
      const step = t => {
        const p = Math.min((t - t0) / 1300, 1);
        el.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))) + suf;
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
    o.observe(el);
  });
  // Destello dorado que sigue al mouse
  document.querySelectorAll('.spot').forEach(el => el.addEventListener('pointermove', e => {
    const r = el.getBoundingClientRect();
    el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
    el.style.setProperty('--my', (e.clientY - r.top) + 'px');
  }));
  // Inclinación 3D suave de la tarjeta del hero
  const card = document.querySelector('.sample'), hero = document.querySelector('.hero');
  if (card && hero && !reduce && matchMedia('(hover:hover)').matches) {
    hero.addEventListener('pointermove', e => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - (r.left + r.width / 2)) / r.width;
      const y = (e.clientY - (r.top + r.height / 2)) / r.height;
      card.style.transform = `perspective(900px) rotateY(${x * 9}deg) rotateX(${-y * 9}deg)`;
    });
    hero.addEventListener('pointerleave', () => card.style.transform = '');
  }
  // Menú accesible para móviles
  const toggle = document.querySelector('.nav-toggle');
  const menu = document.querySelector('#main-nav');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      toggle.setAttribute('aria-label', open ? 'Abrir menú' : 'Cerrar menú');
      menu.classList.toggle('is-open', !open);
      document.body.classList.toggle('menu-open', !open);
    });
    menu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'Abrir menú');
      menu.classList.remove('is-open');
      document.body.classList.remove('menu-open');
    }));
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', 'Abrir menú');
        menu.classList.remove('is-open');
        document.body.classList.remove('menu-open');
      }
    });
  }
  // Barra de navegación
  const nav = document.querySelector('.nav');
  const f = () => nav.classList.toggle('scrolled', scrollY > 24);
  f(); addEventListener('scroll', f, { passive: true });
})();
