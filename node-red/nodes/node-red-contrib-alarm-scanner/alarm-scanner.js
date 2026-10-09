module.exports = function(RED) {
    const AlarmScanner = require('./AlarmScanner');

    function AlarmScannerNode(config) {
        RED.nodes.createNode(this, config);
         // Create a new AlarmScanner instance for each input
        const scanner = new AlarmScanner();
        const node = this;

        node.on('input', function(msg) {
            if (typeof msg.payload === 'object' && msg.payload !== null) {

                const tagInfo = msg.payload;

                const result = scanner.update(tagInfo);
                msg.alarms = result;
                msg.alarmState = scanner.tag.ALARM;
                msg.fail = scanner.tag.FAIL;
                node.send(msg);
            } else {
                node.error("Input payload must be a JSON object with tag information");
            }
        });
    }

    RED.nodes.registerType("alarm-scanner", AlarmScannerNode);
}
