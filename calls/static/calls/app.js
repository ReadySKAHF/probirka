(function () {
    'use strict';

    var root = document.documentElement;
    var REFRESH_MS = 30000;

    var store = {
        get: function (key, fallback) {
            try {
                var value = localStorage.getItem(key);
                return value === null ? fallback : value;
            } catch (e) { return fallback; }
        },
        set: function (key, value) {
            try { localStorage.setItem(key, value); } catch (e) {}
        },
        getJSON: function (key, fallback) {
            try { return JSON.parse(store.get(key, '')) || fallback; } catch (e) { return fallback; }
        },
        setJSON: function (key, value) { store.set(key, JSON.stringify(value)); }
    };

    function $(selector, scope) { return (scope || document).querySelector(selector); }
    function $all(selector, scope) { return Array.prototype.slice.call((scope || document).querySelectorAll(selector)); }

    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (key) {
            if (key === 'className') node.className = attrs[key];
            else if (key === 'text') node.textContent = attrs[key];
            else node.setAttribute(key, attrs[key]);
        });
        (children || []).forEach(function (child) {
            node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
        });
        return node;
    }

    function icon(name, extraClass) {
        var ns = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('class', 'icon' + (extraClass ? ' ' + extraClass : ''));
        var use = document.createElementNS(ns, 'use');
        use.setAttribute('href', '#i-' + name);
        svg.appendChild(use);
        return svg;
    }

    function toast(message) {
        var box = $('.toasts');
        var item = el('div', { className: 'toast', text: message });
        box.appendChild(item);
        setTimeout(function () { item.remove(); }, 2200);
    }

    function isTyping(target) {
        return target && (/^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName) || target.isContentEditable);
    }

    function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        // Clipboard API недоступен по http не на localhost
        return new Promise(function (resolve, reject) {
            var area = el('textarea', { style: 'position:fixed;opacity:0' });
            area.value = text;
            document.body.appendChild(area);
            area.select();
            var ok = document.execCommand('copy');
            area.remove();
            if (ok) resolve(); else reject();
        });
    }

    function copyButton(value) {
        return el('button', { type: 'button', className: 'cell-copy', 'data-copy': value, title: 'Копировать' },
            [icon('copy', 'icon-sm')]);
    }

    function toggleTheme() {
        var next = root.dataset.theme === 'dark' ? 'light' : 'dark';
        root.dataset.theme = next;
        store.set('cv.theme', next);
    }

    var mobileQuery = window.matchMedia('(max-width: 900px)');

    function toggleSidebar() {
        if (mobileQuery.matches) {
            root.classList.toggle('sidebar-open');
            return;
        }
        var collapsed = root.classList.toggle('sidebar-collapsed');
        store.set('cv.sidebar', collapsed ? 'collapsed' : 'open');
    }

    var hiddenColsStyle = el('style');
    document.head.appendChild(hiddenColsStyle);

    function getHiddenCols() { return store.getJSON('cv.hiddenCols', []); }

    function applyHiddenCols() {
        var hidden = getHiddenCols();
        hiddenColsStyle.textContent = hidden.map(function (key) {
            return '[data-col="' + key + '"]{display:none}';
        }).join('');
        $all('[data-col-toggle]').forEach(function (box) {
            box.checked = hidden.indexOf(box.dataset.colToggle) === -1;
        });
    }

    function onColumnToggle(box) {
        var hidden = getHiddenCols().filter(function (key) { return key !== box.dataset.colToggle; });
        if (!box.checked) hidden.push(box.dataset.colToggle);
        store.setJSON('cv.hiddenCols', hidden);
        applyHiddenCols();
    }

    function visibleColumns() {
        var hidden = getHiddenCols();
        return $all('[data-col-toggle]')
            .map(function (box) { return box.dataset.colToggle; })
            .filter(function (key) { return hidden.indexOf(key) === -1; });
    }

    function onExport(link) {
        var url = new URL(link.href, location.href);
        var cols = visibleColumns();
        if (cols.length) url.searchParams.set('cols', cols.join(','));
        link.href = url.toString();
        toast('Готовлю CSV…');
    }

    var refreshTimer = null;

    function scheduleRefresh() {
        clearTimeout(refreshTimer);
        refreshTimer = setTimeout(function () {
            if (isTyping(document.activeElement) || $('.drawer.is-open')) {
                scheduleRefresh();
                return;
            }
            try { sessionStorage.setItem('cv.scroll', String(window.scrollY)); } catch (e) {}
            location.reload();
        }, REFRESH_MS);
    }

    function applyAutorefresh() {
        var button = $('[data-action="toggle-autorefresh"]');
        if (!button) return;
        var on = store.get('cv.autorefresh', '0') === '1';
        button.classList.toggle('is-on', on);
        $('.autorefresh-label', button).textContent = on ? 'Авто · 30 с' : 'Авто';
        if (on) scheduleRefresh(); else clearTimeout(refreshTimer);
    }

    function toggleAutorefresh() {
        var on = store.get('cv.autorefresh', '0') !== '1';
        store.set('cv.autorefresh', on ? '1' : '0');
        applyAutorefresh();
        toast(on ? 'Автообновление каждые 30 с включено' : 'Автообновление выключено');
    }

    function restoreScroll() {
        try {
            var y = sessionStorage.getItem('cv.scroll');
            if (y !== null) {
                sessionStorage.removeItem('cv.scroll');
                window.scrollTo(0, Number(y));
            }
        } catch (e) {}
    }

    var drawer = $('.drawer');
    var drawerBody = $('.drawer-body');

    function detailUrl(baseUrl, id) {
        return baseUrl.replace(/\d+\/?$/, id + '/');
    }

    var SUBSTRING_FIELDS = ['from_ip', 'to_ip'];

    function filterUrl(listUrl, field, value) {
        var params = new URLSearchParams();
        // В кавычках маска ищет значение точно
        params.set(field, SUBSTRING_FIELDS.indexOf(field) === -1 ? '"' + value + '"' : value);
        return listUrl + '?' + params.toString();
    }

    function renderTimeline(items, currentId, baseUrl) {
        return el('ul', { className: 'timeline' }, items.map(function (item) {
            var link = el('a', { href: '#', text: (item.from_number || '—') + ' → ' + (item.to_number || '—') });
            link.addEventListener('click', function (event) {
                event.preventDefault();
                openDrawer(detailUrl(baseUrl, item.id));
            });
            return el('li', { className: item.id === currentId ? 'is-current' : '' }, [
                el('div', { className: 'when', text: item.date + ' ' + item.time + ' · #' + item.id }),
                link
            ]);
        }));
    }

    function renderDetail(data, url) {
        var call = data.call;
        var fields = [
            ['ID', String(call.id)],
            ['Call ID', call.call_id],
            ['Отправитель', call.from_number],
            ['Получатель', call.to_number],
            ['From IP', call.from_ip],
            ['To IP', call.to_ip],
            ['Дата', call.date],
            ['Время', call.time]
        ];

        var grid = el('dl', { className: 'detail-grid' });
        fields.forEach(function (pair) {
            grid.appendChild(el('dt', { text: pair[0] }));
            grid.appendChild(el('dd', { className: 'mono' }, pair[1]
                ? [el('span', { text: pair[1] }), copyButton(pair[1])]
                : [el('span', { className: 'muted', text: '—' })]));
        });

        var actions = el('div', { className: 'detail-actions' });
        [
            ['call_id', call.call_id, 'Все записи Call ID'],
            ['number', call.from_number, 'Звонки отправителя'],
            ['number', call.to_number, 'Звонки получателя'],
            ['from_ip', call.from_ip, 'Звонки с From IP'],
            ['to_ip', call.to_ip, 'Звонки на To IP']
        ].forEach(function (action) {
            if (!action[1]) return;
            actions.appendChild(el('a', { className: 'pill', href: filterUrl(data.list_url, action[0], action[1]), text: action[2] }));
        });

        var nodes = [grid, actions];

        if (data.same_call.length > 1) {
            nodes.push(el('section', { className: 'detail-section' }, [
                el('h3', { text: 'Хронология Call ID (' + data.same_call.length + ')' }),
                renderTimeline(data.same_call, call.id, url)
            ]));
        }
        if (data.between.length) {
            nodes.push(el('section', { className: 'detail-section' }, [
                el('h3', { text: 'Другие звонки между этими номерами (' + data.between.length + ')' }),
                renderTimeline(data.between, call.id, url)
            ]));
        }

        drawerBody.innerHTML = '';
        nodes.forEach(function (node) { drawerBody.appendChild(node); });
    }

    function openDrawer(url) {
        drawer.classList.add('is-open');
        drawer.setAttribute('aria-hidden', 'false');
        drawerBody.innerHTML = '';
        drawerBody.appendChild(el('p', { className: 'drawer-loading', text: 'Загрузка…' }));
        fetch(url, { headers: { 'Accept': 'application/json' } })
            .then(function (response) {
                if (!response.ok) throw new Error(response.status);
                return response.json();
            })
            .then(function (data) { renderDetail(data, url); })
            .catch(function () {
                drawerBody.innerHTML = '';
                drawerBody.appendChild(el('p', { className: 'muted', text: 'Не удалось загрузить запись' }));
            });
    }

    function closeDrawer() {
        drawer.classList.remove('is-open');
        drawer.setAttribute('aria-hidden', 'true');
    }

    function rows() { return $all('.calls-table tbody tr[data-url]'); }

    function focusRow(row) {
        rows().forEach(function (r) { r.classList.remove('is-focused'); });
        if (!row) return;
        row.classList.add('is-focused');
        row.focus({ preventScroll: true });
        row.scrollIntoView({ block: 'nearest' });
    }

    function moveFocus(step) {
        var list = rows();
        if (!list.length) return;
        var current = list.indexOf($('.calls-table tr.is-focused'));
        var next = current === -1 ? 0 : Math.min(list.length - 1, Math.max(0, current + step));
        focusRow(list[next]);
        if (drawer.classList.contains('is-open')) openDrawer(list[next].dataset.url);
    }

    function startLoading() { root.classList.add('is-loading'); }

    window.addEventListener('pageshow', function () {
        // При возврате «Назад» страница берётся из кэша вместе с блокировками после сабмита
        root.classList.remove('is-loading');
        $all('#filter-form [disabled], [form="filter-form"][disabled]').forEach(function (field) {
            field.disabled = false;
        });
    });

    var actions = {
        'toggle-theme': toggleTheme,
        'toggle-sidebar': toggleSidebar,
        'toggle-autorefresh': toggleAutorefresh,
        'close-drawer': closeDrawer,
        'show-help': function () { $('.help-dialog').showModal(); }
    };

    document.addEventListener('click', function (event) {
        var target = event.target;

        var copy = target.closest('[data-copy]');
        if (copy) {
            event.stopPropagation();
            copyText(copy.dataset.copy).then(function () { toast('Скопировано: ' + copy.dataset.copy); });
            return;
        }

        var actionNode = target.closest('[data-action]');
        if (actionNode) {
            var name = actionNode.dataset.action;
            if (name === 'export') { onExport(actionNode); return; }
            if (actions[name]) { event.preventDefault(); actions[name](); }
            return;
        }

        var row = target.closest('.calls-table tbody tr[data-url]');
        if (row && !target.closest('a, button')) {
            focusRow(row);
            openDrawer(row.dataset.url);
            return;
        }

        $all('details.menu[open]').forEach(function (menu) {
            if (!menu.contains(target)) menu.removeAttribute('open');
        });

        var link = target.closest('a[href]');
        if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey
            && link.origin === location.origin && link.getAttribute('href') !== '#') {
            startLoading();
        }
    });

    document.addEventListener('change', function (event) {
        var target = event.target;
        if (target.matches('[data-col-toggle]')) onColumnToggle(target);
        if (target.matches('[data-autosubmit]')) { startLoading(); target.form.submit(); }
    });

    var filterForm = $('#filter-form');
    if (filterForm) {
        filterForm.addEventListener('submit', function () {
            $all('input, select', filterForm).concat($all('[form="filter-form"]')).forEach(function (field) {
                if (field.name && !field.value) field.disabled = true;
            });
            startLoading();
            setTimeout(function () {
                $all('[type="submit"]', filterForm).forEach(function (b) { b.disabled = true; });
            }, 0);
        });
    }

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            if (isTyping(event.target)) { event.target.blur(); return; }
            if (drawer.classList.contains('is-open')) { closeDrawer(); return; }
            root.classList.remove('sidebar-open');
            return;
        }
        if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
        if ($('.help-dialog[open]')) return;

        if (event.key === '?' || (event.code === 'Slash' && event.shiftKey)) {
            event.preventDefault();
            $('.help-dialog').showModal();
            return;
        }

        // event.code — физическая клавиша, работает в любой раскладке
        switch (event.code) {
            case 'Slash':
                event.preventDefault();
                $('.quick-search input').focus();
                return;
            case 'KeyJ': moveFocus(1); return;
            case 'KeyK': moveFocus(-1); return;
            case 'KeyF': toggleSidebar(); return;
        }

        switch (event.key) {
            case 'Enter':
                var focused = $('.calls-table tr.is-focused');
                if (focused) openDrawer(focused.dataset.url);
                break;
            case 'ArrowLeft':
            case 'ArrowRight':
                var rel = event.key === 'ArrowLeft' ? 'prev' : 'next';
                var pageLink = $('.pagination a[rel="' + rel + '"]');
                if (pageLink) { startLoading(); location.href = pageLink.href; }
                break;
        }
    });

    applyHiddenCols();
    applyAutorefresh();
    restoreScroll();
}());
