class AlarmScanner {
  static OFFSET = 0.1;
  static SENSOR_FAILURE_VALUE = -9999;

  constructor() {

    this.inAlarm = false;
    this.inFailure = false;
    this.lastFailure = false;
    this.latsAlarma = "";
  }


  update(tag) {
    this.tag = tag;
    this.limits = {
      highHigh: tag.HH,
      high: tag.H,
      low: tag.L,
      lowLow: tag.LL
    };


    if (this.inFailure == true) return [];
    const pv = this.getValidPV();
    const alarmState = this.checkAlarmState(pv);
    this.updateTagProperties(alarmState);
    //console.log("state:  "+alarmState + " inAlarm: "+ this.inAlarm);

    if (alarmState != this.latsAlarma && alarmState !== "normal") {
      this.latsAlarma = alarmState;
      this.inAlarm = true;
      return this.createAlarmData(alarmState, pv);
    }

    if (alarmState == "normal" && this.inAlarm===true) {
      this.inAlarm = false;
      return [];
    }

    return [];

  }

  getValidPV() {
    return typeof this.tag.PV === 'number' ? this.tag.PV : AlarmScanner.SENSOR_FAILURE_VALUE;
  }

  checkAlarmState(pv) {
    if (pv === AlarmScanner.SENSOR_FAILURE_VALUE && !this.inFailure) {
      this.inFailure = true;
      return "sensor-failure";
    }

    if (this.isHighHighAlarm(pv)) return "high-high";
    if (this.isHighAlarm(pv)) return "high";
    if (this.isLowAlarm(pv)) return "low";
    if (this.isLowLowAlarm(pv)) return "low-low";
    if (this.inFailure) this.inFailure = false;
    this.latsAlarma = "";
    this.inAlarm = false;
    return "normal";
  }

  isHighHighAlarm(pv) {
    return pv >= this.limits.highHigh && this.tag.enableHH;
  }

  isHighAlarm(pv) {
    return pv >= this.limits.high - AlarmScanner.OFFSET && pv < this.limits.highHigh && this.tag.enableH;
  }

  isLowAlarm(pv) {
    return pv <= this.limits.low + AlarmScanner.OFFSET && pv > this.limits.lowLow && this.tag.enableL;
  }

  isLowLowAlarm(pv) {
    return pv <= this.limits.lowLow && this.tag.enableLL;
  }

  updateTagProperties(alarmState) {
    this.inAlarm = alarmState !== "normal";
    this.tag.FAIL = this.inAlarm ? 1 : 0;
    this.tag.ALARM = this.getAlarmColor(alarmState);
  }

  getAlarmColor(alarmState) {
    switch (alarmState) {
      case "normal": return "#1c491d";
      case "high":
      case "low": return "#9d891d";
      default: return "#8E0000";
    }
  }

  createAlarmData(alarmState, pv) {
    if (alarmState === "normal") return [];
    if (this.latsAlarma === this.inAlarm) return [];
    const date = this.obtenerFechaHoraFormateada();
    return [{
      DATE: date,
      TAG: this.tag.TagName,
      Valor: pv,
      Descripcion: this.tag.Descripcion,
      Alerta: this.getAlertMessage(alarmState),
      AlarmColor: this.tag.ALARM,
      Unidad: this.tag.und,
    }];

  }

  getAlertMessage(alarmState) {

    const prefix = {
      "high-high": "Muy Alta",
      "high": "Alta",
      "low": "Baja",
      "low-low": "Muy Baja",
      "sensor-failure": "Sensor en falla"
    }[alarmState];
    return `${this.tag.Descripcion}  ${prefix} ${this.tag.TagName}`;
  }

  obtenerFechaHoraFormateada() {
    const ahora = new Date();

    const dia = String(ahora.getDate()).padStart(2, '0');
    const mes = String(ahora.getMonth() + 1).padStart(2, '0'); // Enero es 0
    const anio = ahora.getFullYear();

    const horas = String(ahora.getHours()).padStart(2, '0');
    const minutos = String(ahora.getMinutes()).padStart(2, '0');
    const segundos = String(ahora.getSeconds()).padStart(2, '0');

    return `${dia}-${mes}-${anio} ${horas}:${minutos}:${segundos}`;
  }
}

module.exports = AlarmScanner;

