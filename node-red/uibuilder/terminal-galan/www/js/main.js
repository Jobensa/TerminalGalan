/* Cliente Terminal Galán (UIBUILDER).
   Migrado desde Node-RED Dashboard 1/2 y node-red-contrib-ui-svg.
   - El SVG principal y el de Raspador se cargan por fetch y se enlazan aquí
     (antes el servidor mandaba set_svg + add_event en la cadena Plantilla SVG/Load SVG).
   - No llamar a uibuilder.start() manualmente: en UIBUILDER v7 el cliente se
     auto-inicia al terminar las cabeceras (evento uibuilder:httpHeadersReady).
   - Parche requerido en node_modules/node-red-contrib-uibuilder/front-end/uibuilder.iife.min.js
     (urlJoin) para el refresco; ver patch-uibuilder-7.7.4/. */

const status = document.getElementById('connection-status');

const views = {
    main: document.getElementById('view-main'),
    raspador: document.getElementById('view-raspador'),
};

/* Selectores de los botones del SVG -> mensaje que se envía al servidor.
   Los ids son únicos dentro de cada SVG; cada vista se enlaza por separado. */
const BUTTONS = {
    main: [
        'PB_LLENAR1', 'PB_PAUSAR1', 'PB_CERRAR1',
        'PB_LLENAR2', 'PB_PAUSAR2', 'PB_CERRAR2',
        'PB_CISTERNA1', 'PB_CISTERNA2',
        'PB_PIT_2001', 'PB_TIT_2001', 'PB_FIT_2001',
        'PB_CREATE_CISTERNA1', 'PB_CREATE_CISTERNA2',
        'PB_UIT_2001_DENSITY',
    ],
    raspador: ['PIT_2002_HH', 'PIT_2002_H', 'SIC_2002_SP'],
};

const SVG_SOURCES = {
    main: './svg/main-display.svg',
    raspador: './svg/raspador.svg',
};

function sendEvent(message) { uibuilder.send(message); }

function bindButtons(viewName) {
    const root = views[viewName];
    if (!root) return;
    BUTTONS[viewName].forEach((id) => {
        const el = root.querySelector('#' + id);
        if (!el) return;
        el.classList.add('tg-clickable');
        el.addEventListener('click', () => sendEvent({ topic: id, payload: id }));
    });
}

function loadSVG(viewName) {
    const root = views[viewName];
    fetch(SVG_SOURCES[viewName])
        .then((response) => {
            if (!response.ok) throw new Error(`SVG HTTP ${response.status}`);
            return response.text();
        })
        .then((svg) => {
            root.innerHTML = svg.replace(/xlink:href/g, 'href');
            bindButtons(viewName);
        })
        .catch((error) => {
            root.innerHTML = `<p class="empty-state">No se pudo cargar ${SVG_SOURCES[viewName]}: ${error.message}</p>`;
            console.error(error);
        });
}

/* ---------- Comandos enviados por el servidor (set_text / set_style_attribute) ---------- */
function applyCommand(command) {
    if (!command || !command.command) return;
    const roots = command.view && views[command.view] ? [views[command.view]] : Object.values(views);
    roots.forEach((root) => {
        let elements = [];
        try { elements = root.querySelectorAll(command.selector); } catch (_) { elements = []; }
        elements.forEach((element) => {
            if (command.command === 'set_text') element.textContent = command.text ?? '';
            if (command.command === 'set_style_attribute') element.style.setProperty(command.attribute, command.value);
            if (command.command === 'add_event') {
                element.addEventListener(command.event || 'click', () => sendEvent(command.message || {}));
            }
        });
    });
}

/* ============================ Navegación ============================ */
document.getElementById('app-nav').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-view]');
    if (!button) return;
    const target = button.dataset.view;
    Object.entries(views).forEach(([name, el]) => {
        if (!el) return;
        const active = name === target;
        el.hidden = !active;
        el.classList.toggle('active', active);
    });
    document.querySelectorAll('#app-nav button').forEach((b) => b.classList.toggle('active', b === button));
});

/* ============================ Popups ============================ */
let activePopup = null;

function closePopup() {
    if (activePopup) { activePopup.remove(); activePopup = null; }
}

function openPopup(title, contentHtml, footerHtml, extraClass = '') {
    closePopup();
    const popup = document.createElement('div');
    popup.id = 'tg-popup';
    popup.className = 'tg-popup-overlay';
    popup.innerHTML = `<section class="tg-popup ${extraClass}" role="dialog" aria-modal="true">
        <header><h2>${title}</h2><button class="tg-close" type="button">×</button></header>
        <div class="tg-popup-content">${contentHtml}</div>
        <footer>${footerHtml}</footer>
    </section>`;
    document.body.appendChild(popup);
    popup.addEventListener('click', (event) => {
        if (event.target === popup || event.target.classList.contains('tg-close')) closePopup();
    });
    activePopup = popup;
    return popup;
}

function fieldValue(popup, name) {
    const input = popup.querySelector(`[name="${name}"]`);
    return input ? input.value : undefined;
}

/* ---------- 1. Formulario de llenado (topic "LLENADO") ---------- */
function showFillPopup(data) {
    const popup = openPopup('Datos de carga', `
        <label>Cliente<input name="cliente" type="text"></label>
        <label>Producto<select name="producto"><option value="">Seleccione</option><option>PROPANO</option><option>BUTANO</option></select></label>
        <label>Cisterna<input name="cisterna" type="text"></label>
        <label>Nro. tiquete<input name="tiquete" type="number"></label>
        <label>Fecha<input name="fecha" type="text"></label>
        <label>RVP<input name="rvp" type="number" step="0.01"></label>
        <label>Volumen objetivo<input name="Vol_full" type="number" step="0.01"></label>`,
        `<button class="tg-cancel" type="button">Cancelar</button><button class="tg-save" type="button">Guardar</button>`);
    Object.entries(data || {}).forEach(([key, value]) => {
        const input = popup.querySelector(`[name="${key}"]`);
        if (input) input.value = value ?? '';
    });
    popup.querySelector('.tg-cancel').onclick = closePopup;
    popup.querySelector('.tg-save').onclick = () => {
        if (!fieldValue(popup, 'producto')) { alert('Por favor seleccione un producto'); return; }
        const payload = {};
        popup.querySelectorAll('[name]').forEach((input) => { payload[input.name] = input.value; });
        ['tiquete', 'rvp', 'Vol_full'].forEach((key) => { if (payload[key] !== '') payload[key] = Number(payload[key]); });
        payload.origen = 'LLENADO';
        uibuilder.send({ topic: 'OK', payload });
        closePopup();
    };
}

/* ---------- 2. Configuración de alarmas (topic "open_alarm_config") ---------- */
function showAlarmPopup(tag) {
    const popup = openPopup(`Configuración de ${tag?.TagName || 'Tag'}`, `
        <div class="tg-pv">PV: <strong>${tag?.PV ?? '---'}</strong> ${tag?.und || ''}</div>
        <label>Tag Name<input name="TagName" type="text"></label>
        <label>Descripción<input name="Descripcion" type="text"></label>
        <label>HH<input name="HH" type="number" step="0.01"></label>
        <label>H<input name="H" type="number" step="0.01"></label>
        <label>L<input name="L" type="number" step="0.01"></label>
        <label>LL<input name="LL" type="number" step="0.01"></label>
        <label>Mínimo<input name="Min" type="number" step="0.01"></label>
        <label>Máximo<input name="Max" type="number" step="0.01"></label>
        <label>Falla<select name="FAIL"><option value="0">Normal</option><option value="1">En falla</option></select></label>`,
        `<button class="tg-cancel" type="button">Cancelar</button><button class="tg-save" type="button">Guardar</button>`);
    Object.entries(tag || {}).forEach(([key, value]) => {
        const input = popup.querySelector(`[name="${key}"]`);
        if (input) input.value = value ?? '';
    });
    popup.querySelector('.tg-cancel').onclick = closePopup;
    popup.querySelector('.tg-save').onclick = () => {
        const payload = { ...tag };
        popup.querySelectorAll('[name]').forEach((input) => {
            payload[input.name] = ['HH', 'H', 'L', 'LL', 'Min', 'Max', 'FAIL'].includes(input.name)
                ? Number(input.value) : input.value;
        });
        uibuilder.send({ topic: 'tag_update', payload });
        closePopup();
    };
}

/* ---------- 3. Confirmación genérica (topic "ui_confirm") ----------
   El servidor manda payload {text, context}; se devuelve {result, context}
   para que UIB Router / UIB Confirm enruten a la acción correcta. */
function showConfirmPopup(data) {
    const text = typeof data === 'string' ? data : (data && data.text) || '¿Confirmar acción?';
    const context = (data && typeof data === 'object' && data.context) || '';
    const popup = openPopup('Confirmación', `<p class="tg-text">${text}</p>`,
        `<button class="tg-cancel" type="button">Cancelar</button><button class="tg-save" type="button">Aceptar</button>`);
    popup.querySelector('.tg-cancel').onclick = () => {
        uibuilder.send({ topic: 'ui_confirm', payload: { result: 'cancel', context } });
        closePopup();
    };
    popup.querySelector('.tg-save').onclick = () => {
        uibuilder.send({ topic: 'ui_confirm', payload: { result: 'ok', context } });
        closePopup();
    };
}

/* ---------- 4. Edición de setpoint (topic "ui_setpoint") ---------- */
function showSetpointPopup(data) {
    const popup = openPopup(data?.label || 'Editar valor', `
        <label class="tg-full">${data?.label || 'Valor'} (${data?.suffix || ''})
            <input name="value" type="number" step="0.01"></label>`,
        `<button class="tg-cancel" type="button">Cancelar</button><button class="tg-save" type="button">Aplicar</button>`);
    const input = popup.querySelector('[name="value"]');
    input.value = data?.currentValue ?? '';
    input.focus();
    popup.querySelector('.tg-cancel').onclick = closePopup;
    popup.querySelector('.tg-save').onclick = () => {
        const value = Number(input.value);
        if (Number.isNaN(value)) { alert('Ingrese un valor numérico'); return; }
        uibuilder.send({ topic: 'ui_setpoint', payload: { tag: data?.tag, value, context: data?.context } });
        closePopup();
    };
}

/* ---------- 5. Gestión de cisternas (topics LISTA_CISTERNAS / EDIT_CISTERNA / OPEN_POPUP / REFRESH_LISTA) ---------- */
const cisternas = { list: [], filtro: '', seleccionada: null, listPopup: null };

function cisternasFiltradas() {
    if (!cisternas.filtro) return cisternas.list;
    const f = cisternas.filtro.toLowerCase();
    return cisternas.list.filter((c) =>
        (c.placa && String(c.placa).toLowerCase().includes(f)) ||
        (c.cliente && String(c.cliente).toLowerCase().includes(f)));
}

function renderCisternasTable() {
    if (!cisternas.listPopup) return;
    const tbody = cisternas.listPopup.querySelector('tbody');
    if (!tbody) return;
    const rows = cisternasFiltradas();
    tbody.innerHTML = rows.map((c) => `
        <tr data-id="${c.id}" class="${cisternas.seleccionada && cisternas.seleccionada.id === c.id ? 'seleccionada' : ''}">
            <td>${c.id ?? ''}</td>
            <td><strong>${c.placa ?? ''}</strong></td>
            <td>${c.cliente ?? ''}</td>
            <td>${c.capacidad ? Number(c.capacidad).toLocaleString() : '0'}</td>
            <td>${String(c.activa) === '1' ? '<span class="estado-activo">✔ Activa</span>' : '<span class="estado-inactivo">✖ Inactiva</span>'}</td>
            <td class="tg-acciones">
                <button class="tg-mini tg-edit" type="button" title="Editar">✏️</button>
                <button class="tg-mini tg-del" type="button" title="Eliminar">🗑️</button>
            </td>
        </tr>`).join('') + (rows.length === 0 ? '<tr><td colspan="6" class="sin-datos">No se encontraron cisternas</td></tr>' : '');
    tbody.querySelectorAll('tr[data-id]').forEach((tr) => {
        const data = cisternas.list.find((x) => String(x.id) === tr.dataset.id);
        tr.addEventListener('click', () => { cisternas.seleccionada = data; renderCisternasTable(); });
        tr.addEventListener('dblclick', () => {
            uibuilder.send({ topic: 'CISTERNA_SELECCIONADA', payload: { ...data } });
            closePopup();
        });
        tr.querySelector('.tg-edit').addEventListener('click', (e) => { e.stopPropagation(); showCisternaForm(data); });
        tr.querySelector('.tg-del').addEventListener('click', (e) => {
            e.stopPropagation();
            if (!confirm(`¿Está seguro de eliminar la cisterna ${data.placa}?`)) return;
            uibuilder.send({ topic: 'DELETE', payload: { ...data } });
            cisternas.list = cisternas.list.filter((x) => x.id !== data.id);
            renderCisternasTable();
        });
    });
}

function showCisternasList(data) {
    cisternas.list = Array.isArray(data) ? data : [];
    cisternas.filtro = '';
    cisternas.seleccionada = null;
    const popup = openPopup('📋 Lista de Cisternas', `
        <div class="tg-lista">
            <div class="busqueda">
                <input type="text" class="tg-filtro" placeholder="🔍 Buscar por placa o cliente...">
                <div class="hint">💡 Doble click para seleccionar cisterna e iniciar llenado</div>
            </div>
            <div class="tabla-container">
                <table class="tabla-cisternas">
                    <thead><tr><th>ID</th><th>Placa</th><th>Cliente</th><th>Capacidad (L)</th><th>Estado</th><th>Acciones</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>`,
        `<button class="tg-cancel" type="button">Cerrar</button><button class="tg-new" type="button">+ Nueva Cisterna</button>`,
        'tg-popup-wide');
    cisternas.listPopup = popup;
    popup.querySelector('.tg-cancel').onclick = closePopup;
    popup.querySelector('.tg-new').onclick = () => showCisternaForm(null);
    popup.querySelector('.tg-filtro').addEventListener('input', (e) => { cisternas.filtro = e.target.value; renderCisternasTable(); });
    renderCisternasTable();
}

function showCisternaForm(data) {
    const isNew = !(data && data.id);
    const c = isNew
        ? { id: null, placa: '', cliente: '', capacidad: 0, activa: 1 }
        : { ...data };
    const disabled = isNew ? '' : 'disabled';
    const popup = openPopup(isNew ? '➕ Nueva Cisterna' : '✏️ Gestionar Cisterna', `
        <label>Placa (única)<input name="placa" type="text" ${disabled}></label>
        <label>Cliente<input name="cliente" type="text" ${disabled}></label>
        <label>Capacidad (GAL)<input name="capacidad" type="number" ${disabled}></label>
        <label class="tg-check"><input name="activa" type="checkbox" ${disabled}> Cisterna activa</label>`,
        `<button class="tg-cancel" type="button">Cancelar</button>
         ${isNew ? '' : '<button class="tg-del-form tg-del" type="button">Borrar</button><button class="tg-edit-form" type="button">Editar</button>'}
         <button class="tg-save" type="button">${isNew ? 'Guardar' : 'Guardar'}</button>`);
    popup.querySelector('[name="placa"]').value = c.placa ?? '';
    popup.querySelector('[name="cliente"]').value = c.cliente ?? '';
    popup.querySelector('[name="capacidad"]').value = c.capacidad ?? 0;
    popup.querySelector('[name="activa"]').checked = String(c.activa) === '1' || c.activa === true;
    popup.querySelector('.tg-cancel').onclick = closePopup;

    const enableEdit = () => popup.querySelectorAll('[name]').forEach((i) => { i.disabled = false; });
    const editBtn = popup.querySelector('.tg-edit-form');
    if (editBtn) editBtn.onclick = enableEdit;

    const delForm = popup.querySelector('.tg-del-form');
    if (delForm) delForm.onclick = () => {
        if (!confirm('¿Está seguro de eliminar esta cisterna?')) return;
        uibuilder.send({ topic: 'DELETE', payload: { ...c } });
        closePopup();
    };

    popup.querySelector('.tg-save').onclick = () => {
        const payload = { ...c };
        popup.querySelectorAll('[name]').forEach((input) => {
            if (input.name === 'activa') payload.activa = input.checked ? 1 : 0;
            else payload[input.name] = input.name === 'capacidad' ? (parseFloat(input.value) || 0) : input.value;
        });
        if ((isNew || !delForm) && !payload.placa) { alert('La placa es obligatoria.'); return; }
        uibuilder.send({ topic: isNew ? 'INSERT' : 'UPDATE', payload });
        closePopup();
    };
}

function updateCisternasList(data) {
    if (!cisternas.listPopup) return;
    cisternas.list = Array.isArray(data) ? data : cisternas.list;
    renderCisternasTable();
}

/* ---------- 6. Tiquete LPG (topic "TIQUETE_LPG") ---------- */
function esc(value) {
    return String(value === null || value === undefined ? '' : value)
        .replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function fmt(value, decimals) {
    if (value === null || value === undefined || value === '') return '---';
    const n = Number(value);
    return Number.isNaN(n) ? esc(value) : n.toFixed(decimals);
}

function tiqueteRow(label, value, unit) {
    return `<div class="tiquete-row"><span class="label">${label}</span><span class="value">${value}</span><span class="unit">${unit || ''}</span></div>`;
}

function buildTiquete(datos) {
    const input = datos.input || {};
    const corrections = datos.corrections || {};
    const volumes = datos.volumes || {};
    const gravedadAPI = corrections.standardDensity_SG ? (141.5 / corrections.standardDensity_SG) - 131.5 : 0;
    const empresa = esc(datos.empresa || 'PETROSANTANDER COLOMBIA INC');
    return `
    <div class="tiquete-container">
      <div class="tiquete-header">
        <h1>${esc(datos.empresa || 'PETROSANTANDER COLOMBIA INC')}</h1>
        <h2>PLANTA DE PRODUCTOS BLANCOS</h2>
        <h2>REPORTE DE BATCH</h2>
      </div>
      <div class="tiquete-info">
        <div>
          <div>PLANTA DE GAS</div>
          <div>ESTACION DE BOMBEO GLP</div>
          <div>Cliente: <b>${esc(datos.cliente || 'N/A')}</b></div>
          <div>Origen: ${esc(datos.origen || 'PETROSANTANDER')}</div>
        </div>
        <div style="text-align: right;">
          <div>Numero de Tiquete: <b>${esc(datos.numeroTiquete || '---')}</b></div>
          <div>Fecha: <b>${esc(datos.fechaHora)}</b></div>
          <div>Operación: ${esc(datos.operacion || 'Ventas')}</div>
          <div>Bala: ${esc(datos.bala || 'BA - 1')}</div>
        </div>
      </div>
      <div class="tiquete-stream">STREAM ${esc(datos.stream || '1')} - MEDIDOR ${esc(datos.tipoMedidor || 'CORIOLIS')}</div>
      <div class="tiquete-section">
        <div class="tiquete-section-title">DATOS DEL PRODUCTO</div>
        ${tiqueteRow('Producto', esc((input.fluid || '').toUpperCase()), '')}
        ${tiqueteRow('Densidad Relativa Observada', fmt(input.observedDensity_SG, 4), 'SG')}
        ${tiqueteRow('Temperatura Observada', fmt(input.observedTemp_F, 2), 'Deg.F')}
        ${tiqueteRow('Presion de Vapor (RVP)', fmt(input.rvp, 2), 'psig')}
        ${tiqueteRow('Presion de Equilibrio', fmt(corrections.Pe_PSIG, 2), 'psig')}
      </div>
      <div class="tiquete-section">
        <div class="tiquete-section-title">DATOS DEL MEDIDOR</div>
        ${tiqueteRow('Pulsos Batch', esc(datos.pulsosBatch || '---'), 'pulsos')}
        ${tiqueteRow('K-Factor', esc(datos.kFactor || '14000.00'), 'pulsos/bbl')}
        ${tiqueteRow('M-Factor', fmt(input.mFactor, 4), '')}
        ${tiqueteRow('Temperatura Promedio', fmt(input.observedTemp_F, 2), 'Deg.F')}
        ${tiqueteRow('Presion Promedio', fmt(input.observedPressure_PSIG, 2), 'psig')}
      </div>
      <div class="tiquete-section">
        <div class="tiquete-section-title">CALCULOS</div>
        ${tiqueteRow('Tabla Utilizada', 'GPA - TP27', '')}
        ${tiqueteRow('Densidad Relativa @ 60F', fmt(corrections.standardDensity_SG, 4), 'SG')}
        ${tiqueteRow('Gravedad API', fmt(gravedadAPI, 1), 'API Degrees')}
        ${tiqueteRow('CTL Factor', fmt(corrections.Ctl, 4), '')}
        ${tiqueteRow('CPL Factor', fmt(corrections.Cpl, 4), '')}
        ${tiqueteRow('CCF Factor Combinado', fmt(corrections.CCF, 4), '')}
      </div>
      <div class="tiquete-section tiquete-totales">
        <div class="tiquete-section-title">TOTALES</div>
        ${tiqueteRow('Volumen Indicado (IV)', fmt(volumes.indicated_USgal, 2), 'U.S.gal')}
        ${tiqueteRow('Volumen Bruto (GUV)', fmt(volumes.gross_USgal, 2), 'U.S.gal')}
        ${tiqueteRow('Volumen Estandar (GSV)', fmt(volumes.standard_USgal, 2), 'U.S.gal')}
        ${tiqueteRow('Masa', fmt(volumes.mass_kg, 2), 'kg')}
      </div>
      <div class="tiquete-separator"></div>
      <div class="tiquete-footer">
        <div class="tiquete-firmas">
          <div class="tiquete-firma"><div class="tiquete-firma-linea">OPERADOR</div></div>
          <div class="tiquete-firma">
            <div class="tiquete-logo">${empresa}<br><span class="tiquete-despachado">DESPACHADO</span></div>
            <div class="tiquete-firma-linea">SUPERVISOR</div>
          </div>
        </div>
      </div>
    </div>`;
}

const PRINT_CSS = `
  body { font-family: 'Courier New', monospace; font-size: 11px; }
  .tiquete-container { max-width: 400px; margin: 0 auto; }
  .tiquete-header { text-align: center; border-bottom: 2px double #000; padding-bottom: 8px; margin-bottom: 8px; }
  .tiquete-header h1 { font-size: 12px; margin: 0; letter-spacing: 2px; }
  .tiquete-header h2 { font-size: 11px; margin: 3px 0; font-weight: normal; }
  .tiquete-info { display: flex; justify-content: space-between; border-bottom: 1px solid #000; padding: 5px 0; margin-bottom: 8px; font-size: 10px; }
  .tiquete-section { margin-bottom: 10px; }
  .tiquete-section-title { font-weight: bold; border-bottom: 1px dashed #999; margin-bottom: 5px; }
  .tiquete-row { display: flex; justify-content: space-between; padding: 1px 0; }
  .tiquete-row .label { flex: 1; }
  .tiquete-row .value { text-align: right; min-width: 80px; font-weight: bold; }
  .tiquete-row .unit { text-align: left; min-width: 70px; padding-left: 8px; }
  .tiquete-totales { background: #f0f0f0; padding: 8px; border: 1px solid #ccc; }
  .tiquete-separator { border-top: 2px double #000; margin: 10px 0; }
  .tiquete-stream { text-align: center; font-weight: bold; margin: 8px 0; background: #eee; padding: 3px; }
  .tiquete-firmas { display: flex; justify-content: space-between; margin-top: 20px; }
  .tiquete-firma { text-align: center; width: 45%; }
  .tiquete-firma-linea { border-top: 1px solid #000; margin-top: 30px; padding-top: 3px; }
  .tiquete-logo { text-align: right; font-weight: bold; color: #0066cc; }
  .tiquete-despachado { color: #0066cc; font-weight: bold; font-size: 14px; }`;

function printTiquete() {
    const contenedor = document.querySelector('#tg-popup .tiquete-container');
    if (!contenedor) return;
    const ventana = window.open('', '_blank');
    ventana.document.write(`<html><head><title>Tiquete LPG</title><style>${PRINT_CSS}</style></head>
        <body><div class="tiquete-container">${contenedor.innerHTML}</div></body></html>`);
    ventana.document.close();
    ventana.focus();
    ventana.print();
}

function showTicketPopup(datos) {
    if (!datos || typeof datos !== 'object' || Array.isArray(datos)) return;
    const popup = openPopup('Tiquete LPG', buildTiquete(datos),
        `<button class="tg-cancel" type="button">Cerrar</button>
         <button class="tg-print" type="button">🖨️ Imprimir</button>`, 'tg-popup-ticket');
    popup.querySelector('.tg-cancel').onclick = closePopup;
    popup.querySelector('.tg-print').onclick = printTiquete;
}

/* ---------- 7. Notificaciones (topic "ui_notify") ---------- */
function showToast(message) {
    const cont = document.getElementById('tg-toasts');
    const toast = document.createElement('div');
    toast.className = 'tg-toast';
    toast.textContent = (message && message.text) || (typeof message === 'string' ? message : JSON.stringify(message));
    cont.appendChild(toast);
    setTimeout(() => toast.classList.add('visible'), 10);
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 400);
    }, 5000);
}

/* ============================ Mensajes del servidor ============================ */
function handlePopupMessage(msg) {
    const { topic, payload } = msg;
    if (topic === 'LLENADO' && payload && !Array.isArray(payload)) { showFillPopup(payload); return true; }
    if (topic === 'open_alarm_config' && payload && !Array.isArray(payload)) { showAlarmPopup(payload); return true; }
    if (topic === 'ui_confirm') { showConfirmPopup(payload); return true; }
    if (topic === 'ui_setpoint') { showSetpointPopup(payload); return true; }
    if (topic === 'LISTA_CISTERNAS') { showCisternasList(payload); return true; }
    if (topic === 'EDIT_CISTERNA' || topic === 'OPEN_POPUP') { showCisternaForm(payload); return true; }
    if (topic === 'REFRESH_LISTA') { updateCisternasList(payload); return true; }
    if (topic === 'TIQUETE_LPG') { showTicketPopup(payload); return true; }
    if (topic === 'ui_notify') { showToast(payload); return true; }
    return false;
}

loadSVG('main');
loadSVG('raspador');

uibuilder.onChange('msg', (msg) => {
    if (!msg) return;
    if (handlePopupMessage(msg)) return;
    if (msg.payload !== undefined) {
        const commands = Array.isArray(msg.payload) ? msg.payload : [msg.payload];
        commands.forEach(applyCommand);
    }
});

uibuilder.onChange('ioConnected', (connected) => {
    status.textContent = connected ? 'Conectado' : 'Desconectado';
    const dot = document.getElementById('connection-dot');
    if (dot) {
        dot.classList.toggle('on', !!connected);
        dot.classList.toggle('off', !connected);
    }
});

/* Reloj de la barra lateral (estándar SCADA). */
const clockEl = document.getElementById('clock');
function tickClock() {
    if (clockEl) clockEl.textContent = new Date().toLocaleTimeString('es-CO', { hour12: false });
}
tickClock();
setInterval(tickClock, 1000);
