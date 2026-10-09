

let pit_1001 = global.get("PIT_2001");
let tit_1001 = global.get("TIT_2001");
let dit_1001 = global.get("DIT_2001");
let uit_2001 = global.get("UIT_2001");
let uit_2003 = global.get("UIT_2003");
let status_cisterna1 = global.get("STATUS_CISTERNA1")
let status_cisterna2 = global.get("STATUS_CISTERNA2")
let cisterna1 = global.get("CISTERNA1");
let cisterna2 = global.get("CISTERNA2");
let uit_2001_dit = global.get("UIT_2001_DENSITY");
let segment_display = global.get("SEGMENT_DISPLAY");
let actual_cisterna = global.get("ACTUAL_CISTERNA");
let tiket_number = global.get("TIKET_N") || 0;
let segment1 = global.get("SEGMENT_VALUES1");
let segment2 = global.get("SEGMENT_VALUES2");
let fill_segment1 = global.get("FILL_SEGMENT1");
let fill_segment2 = global.get("FILL_SEGMENT2");
let promedios = global.get("PROMEDIOS");
let sel_cisterna = global.get("SEL_CISTERNA");
let cisterna2_visible = global.get("CISTERNA2_VISIBLE");
let cisterna1_visible = global.get("CISTERNA1_VISIBLE");
let str_status_sisterna1 = "";
let str_status_sisterna2 = "";



msg.payload = {
    // ---- TAGS TIPO TEXT (Valores de Instrumentos) ----
    "PIT_2001_PV": pit_1001.PV,
    "TIT_2001_PV": tit_1001.PV,
    "DIT_2001_PV": dit_1001.PV,
    "UIT_2001_FLOW": uit_2001.FLOW,
    "UIT_2001_TBATCH": uit_2001.TBATCH,
    "UIT_2001_DENS": uit_2001.DENS,
    "UIT_2003_FLOW": uit_2003.FLOW,
    "UIT_2003_DENS": uit_2003.DENS,
    "UIT_2003_TOTAL": uit_2003.TOTAL,

    // ---- TAGS TIPO TEXT (Variables de Cisterna/Brazo 1) ----
    "ID_CISTERNA1_VALUE": cisterna1.number,
    "PRODUCTO1_VALUE": fill_segment1.producto,
    "FECHA1_VALUE": fill_segment1.fecha,
    "CLIENTE1_VALUE": fill_segment1.cliente,
    "TIQUETE1_VALUE": fill_segment1.tiquete,
    "RVP1_VALUE": fill_segment1.rvp,
    "MASA1_VALUE": segment_display.MASA_CORIOLIS,
    "VOL_INDICADO1_VALUE": segment_display.VOLUMEN_INDICADO,
    "VAPORES1_VALUE": { type: "text" },
    "VOL_FULL1_VALUE": fill_segment1.Vol_full,
    "VOL_CURRENT1_VALUE": { type: "text" },
    "TEMPERATURE1_VALUE": { type: "text" },
    "PRESSURE1_VALUE": { type: "text" },

    // ---- TAGS TIPO TEXT (Variables de Cisterna/Brazo 2) ----
    "ID_CISTERNA2_VALUE": { type: "text" },
    "PRODUCTO2_VALUE": fill_segment2.producto,
    "FECHA2_VALUE": fill_segment2.fecha,
    "CLIENTE2_VALUE": fill_segment2.cliente,
    "TIQUETE2_VALUE": fill_segment2.tiquete,
    "RVP2_VALUE": fill_segment2.rvp,
    "MASA2_VALUE": segment_display.MASA_CORIOLIS,
    "VOL_INDICADO2_VALUE": segment_display.VOLUMEN_INDICADO,
    "VAPORES2_VALUE": { type: "text" },
    "VOL_FULL2_VALUE": fill_segment2.Vol_full,
    "VOL_CURRENT2_VALUE": { type: "text" },
    "TEMPERATURE2_VALUE": { type: "text" },
    "PRESSURE2_VALUE": { type: "text" },

    // ---- TAGS TIPO FILL (Rectángulos de fondo/Alarma) ----
    "PIT_2001_BACK": pit_1001.ALARM,
    "TIT_2001_BACK": tit_1001.ALARM,
    "DIT_2001_BACK": dit_1001.ALARM,
    "FIT_2001_FLOW_BACK": UIT_2001_FLOW.ALARM,
    "UIT_2001_DENSITY_BACK": UIT_2001_DENSITY.ALARM
}