# Guía de Migración de Templates - Dashboard 1 a Dashboard 2

## 📋 Resumen

Se han creado versiones migradas de los templates modales de Dashboard 1 a Dashboard 2 usando Vue.js.

---

## 📁 Archivos Creados

### 1. **template_llenado_dashboard2.html**
- **Ubicación:** `/node-red/template_llenado_dashboard2.html`
- **Función:** Modal para datos de carga de cisternas
- **Framework:** Vue.js (Dashboard 2)
- **Tamaño:** ~7,990 caracteres

### 2. **template_analogset_dashboard2.html**
- **Ubicación:** `/node-red/template_analogset_dashboard2.html`
- **Función:** Modal para configuración de tags analógicos
- **Framework:** Vue.js (Dashboard 2)
- **Tamaño:** ~13,353 caracteres

---

## 🔄 Principales Cambios AngularJS → Vue.js

### Sintaxis de Templates

| AngularJS (Dashboard 1) | Vue.js (Dashboard 2) | Descripción |
|-------------------------|----------------------|-------------|
| `ng-model="data.cliente"` | `v-model="data.cliente"` | Binding bidireccional |
| `ng-click="closePopup()"` | `@click="closePopup"` | Event handlers |
| `ng-class="{'active': showPopup}"` | `:class="{'active': showPopup}"` | Clases dinámicas |
| `ng-if="tag"` | `v-if="tag"` | Renderizado condicional |
| `{{tag.PV | number:2}}` | `{{tag.PV.toFixed(2)}}` | Formateo de números |
| `ng-model="tag.enableHH" ng-true-value="1" ng-false-value="0"` | `v-model="tag.enableHH" true-value="1" false-value="0"` | Checkboxes con valores personalizados |

### Estructura del Script

**AngularJS (Dashboard 1):**
```javascript
(function(scope){
  scope.showPopup = false;
  scope.openPopup = function(){...};
  scope.$watch('msg', function(msg){...});
})(scope);
```

**Vue.js (Dashboard 2):**
```javascript
export default {
  data() {
    return {
      showPopup: false
    }
  },
  methods: {
    openPopup() {...}
  },
  watch: {
    msg(newMsg) {...}
  }
}
```

---

## 📊 Comparativa de Funcionalidades

### Template Llenado

| Funcionalidad | Dashboard 1 | Dashboard 2 | Notas |
|---------------|-------------|-------------|-------|
| Abrir modal por mensaje (topic: "LLENADO") | ✅ | ✅ | Idéntico |
| Formulario de 7 campos | ✅ | ✅ | Idéntico |
| Select de producto (PROPANO/BUTANO) | ✅ | ✅ | Idéntico |
| Validación de producto requerido | ✅ | ✅ | Idéntico |
| Backup de datos al cancelar | ✅ | ✅ | Idéntico |
| Envío de mensaje con topic "OK" | ✅ | ✅ | Idéntico |
| Cierre al hacer click en overlay | ✅ | ✅ | Idéntico |
| Reset de formulario al guardar | ✅ | ✅ | Idéntico |
| Conversión de números con `.number` | ❌ | ✅ | **Mejora** |

### Template AnalogSET

| Funcionalidad | Dashboard 1 | Dashboard 2 | Notas |
|---------------|-------------|-------------|-------|
| Abrir modal por mensaje (topic: "open_alarm_config") | ✅ | ✅ | Idéntico |
| Display de PV con formato | ✅ | ✅ | Idéntico |
| 14 campos de configuración | ✅ | ✅ | Idéntico |
| 4 toggles de alarmas (HH, H, L, LL) | ✅ | ✅ | Idéntico |
| Selector de color para ALARM | ✅ | ✅ | Idéntico |
| Toggle de estado FAIL | ✅ | ✅ | Idéntico |
| Normalización de tipos antes de enviar | ✅ | ✅ | Idéntico |
| Backup de datos al cancelar | ✅ | ✅ | Idéntico |
| Envío de mensaje con topic "tag_update" | ✅ | ✅ | Idéntico |
| Exposición de función global | ✅ | ✅ | Idéntico |

---

## 🎨 Estilos y Diseño

### Características Comunes

- **Diseño:** Idéntico en ambas versiones
- **Responsivo:** Media queries para móviles
- **Colores:** Gradientes azules en header, verde en botón guardar
- **Animaciones:** Transiciones suaves en overlay
- **Z-index:** 9999 para aparecer sobre otros elementos

### Mejoras en Dashboard 2

1. **Scoped styles:** Los estilos no afectan a otros componentes
2. **Hover effects:** Efectos mejorados en botones
3. **Focus states:** Estados de foco mejorados en inputs
4. **Transiciones:** Más suaves con CSS moderno

---

## 🔌 Integración en Node-RED

### Paso 1: Crear nodos ui-template

Para cada template, crear un nodo **ui-template** en Node-RED con:

#### Template Llenado

```
Tipo: ui-template
Grupo: 7c72297410240a07 (Gmain en Dashboard 2)
Nombre: LlenadoD2
Order: 6
Width: 1
Height: 1
Template: [Copiar contenido de template_llenado_dashboard2.html]
```

**Configuración del nodo:**
- ✅ Store out messages: TRUE
- ✅ Forward in messages: TRUE
- ✅ Resend on refresh: TRUE
- Template scope: local

**Wires (salida):**
- Conectar al mismo nodo que Dashboard 1: `e513baa3401879b3` (link out "To FormFill")

#### Template AnalogSET

```
Tipo: ui-template
Grupo: 7c72297410240a07 (Gmain en Dashboard 2)
Nombre: AnalogSETD2
Order: 7
Width: 1
Height: 1
Template: [Copiar contenido de template_analogset_dashboard2.html]
```

**Configuración del nodo:**
- ✅ Store out messages: TRUE
- ✅ Forward in messages: TRUE
- ✅ Resend on refresh: TRUE
- Template scope: local

**Wires (salida):**
- Conectar al mismo nodo que Dashboard 1: `ea9da6f09b500e72` (function "preparar query")

---

## 📨 Mensajes de Entrada/Salida

### Template Llenado

**Entrada (para abrir el modal):**
```javascript
{
  topic: "LLENADO",
  payload: {
    cliente: "RAYOGAS SAS",
    producto: "PROPANO",
    cisterna: "ABC123",
    tiquete: 1234,
    fecha: "2026-01-20",
    rvp: 9.5,
    Vol_full: 5000
  }
}
```

**Salida (al guardar):**
```javascript
{
  topic: "OK",
  payload: {
    cliente: "RAYOGAS SAS",
    producto: "PROPANO",
    cisterna: "ABC123",
    tiquete: 1234,
    fecha: "2026-01-20",
    rvp: 9.5,
    Vol_full: 5000,
    origen: "LLENADO"
  }
}
```

### Template AnalogSET

**Entrada (para abrir el modal):**
```javascript
{
  topic: "open_alarm_config",
  payload: {
    ID: 1,
    TagName: "PIT_2001",
    Descripcion: "Presión Vd-01",
    und: "PSI",
    PV: 53.1,
    HH: 100,
    H: 95,
    L: 2,
    LL: 1.5,
    Max: 200,
    Min: 0,
    enableHH: 1,
    enableH: 1,
    enableL: 1,
    enableLL: 1,
    ALARM: "#00ba00",
    FAIL: 0
  }
}
```

**Salida (al guardar):**
```javascript
{
  topic: "tag_update",
  payload: {
    ID: 1,
    TagName: "PIT_2001",
    Descripcion: "Presión Vd-01",
    und: "PSI",
    PV: 53.1,
    HH: 100,
    H: 95,
    L: 2,
    LL: 1.5,
    Max: 200,
    Min: 0,
    enableHH: 1,
    enableH: 1,
    enableL: 1,
    enableLL: 1,
    ALARM: "#ff0000",
    FAIL: 0
  }
}
```

---

## 🧪 Pruebas Recomendadas

### Llenado

1. ✅ Abrir modal desde evento SVG (click en PB_CISTERNA1)
2. ✅ Validar que todos los campos se carguen correctamente
3. ✅ Probar select de producto
4. ✅ Validar error al intentar guardar sin producto
5. ✅ Verificar que los datos se envíen correctamente
6. ✅ Probar botón cancelar (debe restaurar valores)
7. ✅ Probar cierre por overlay
8. ✅ Verificar responsive en móvil

### AnalogSET

1. ✅ Abrir modal desde evento SVG (click en PB_PIT_2001, etc.)
2. ✅ Validar display de PV con formato correcto
3. ✅ Probar todos los toggles de alarmas
4. ✅ Probar selector de color
5. ✅ Probar toggle de FAIL
6. ✅ Verificar que los datos se envíen correctamente
7. ✅ Probar botón cancelar (debe restaurar valores)
8. ✅ Verificar responsive en móvil

---

## ⚠️ Consideraciones Importantes

### 1. Convivencia con Dashboard 1

Los nodos de Dashboard 2 pueden coexistir con Dashboard 1 sin problemas. Ambos pueden estar activos simultáneamente.

### 2. IDs de Elementos

Los IDs y clases CSS deben ser únicos. Los templates usan clases con scope, así que no habrá conflictos.

### 3. Funciones Globales

Ambos templates exponen funciones globales para abrirlos desde JavaScript externo:
- `window.openLlenadoModal()`
- `window.openTagEditor()`

### 4. Validación de Datos

Vue.js maneja mejor la conversión de tipos con `.number` modifier en v-model, lo que reduce errores de tipo.

### 5. Debugging

Para debug, los componentes Vue tienen acceso a `console.log()` normalmente:
```javascript
methods: {
  saveTagChanges() {
    console.log('Guardando tag:', this.tag);
    // ...
  }
}
```

---

## 📝 Próximos Pasos

1. ✅ **Revisar templates** - Archivos HTML creados
2. ⏳ **Crear nodos en Node-RED** - Agregar ui-template a flows.json
3. ⏳ **Conectar wires** - Vincular con nodos existentes
4. ⏳ **Probar funcionalidad** - Verificar apertura y cierre
5. ⏳ **Probar envío de datos** - Verificar que se guarden correctamente
6. ⏳ **Ajustes finales** - Corregir cualquier issue

---

## 🔧 Troubleshooting

### El modal no se abre

- Verificar que el topic del mensaje sea exacto: "LLENADO" o "open_alarm_config"
- Revisar consola del navegador para errores
- Verificar que el nodo tenga "Forward in messages" = TRUE

### Los datos no se envían

- Verificar que el nodo tenga "Store out messages" = TRUE
- Verificar wires de salida
- Revisar consola para errores de JavaScript

### Estilos no se aplican

- Verificar que el `<style scoped>` esté presente
- Refrescar caché del navegador (Ctrl+F5)
- Revisar que no haya conflictos con otros estilos globales

---

## 📞 Soporte

Si encuentras algún problema con la migración, revisa:
1. Consola del navegador (F12 → Console)
2. Debug de Node-RED
3. Mensajes de entrada/salida con debug nodes

---

**Autor:** Claude Code
**Fecha:** 2026-01-20
**Versión:** 1.0
