AlarmScanner = require('./AlarmScanner');
function delay(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
  }
async function main() {

	let tag={
		"ID":0,
		"TagName":"PIT_01",
		"Descripcion":"Transmisor de Presion",
		"und": "bar",
		"PV": 0.0,
		"HH": 99.0,
		"H"	:40.0,
		"L"	:10.0,
		"LL":	5.0,
		"Max":	560,
		"Min":0,
		"enableHH":	1,
		"enableH" : 1,
		"enableL" : 1,
		"enableLL": 1,
		"ALARM":	"#00f800",
		"FAIL" : 0,
	}


    const scanner = new AlarmScanner();
	let count=100;	

	while (count>0) {		

		count-=5;
		let result = scanner.update(tag);
		console.log (result);			
		tag.PV=count;
		

		//console.log(tag);

		await delay(500);
		
		
	}

	

    
}


main();