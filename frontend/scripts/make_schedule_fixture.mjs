// Writes tests/fixtures/schedule-3-days.xlsx: a Czech AD's shooting schedule (title row, Czech headers,
// three days with dates, pages in eighths and whole pages, a location that does not exist yet, cast names).
import * as XLSX from "xlsx";
const rows = [
  ["Noc na Karlštejně – harmonogram"], [],
  ["Den", "Datum", "Obraz", "Int/Ext", "D/N", "Motiv", "Str.", "Lokace", "Herci"],
  [1, "5.1.2099", "42", "EXT", "DEN", "NÁBŘEŽÍ – Marta najde loď", "1 6/8", "Nábřeží Troja", "Anna Geislerová, Jiří Mádl"],
  [1, "5.1.2099", "43", "EXT", "DEN", "NÁBŘEŽÍ – Jonas vesluje", "6/8", "Nábřeží Troja", "Jiří Mádl"],
  [2, "6.1.2099", "17", "INT", "DEN", "CHALUPA – kuchyň, dopis", "2 5/8", "Chalupa Sedlec", "Anna Geislerová, Iva Janžurová"],
  [2, "6.1.2099", "18", "INT", "NOC", "CHALUPA – kuchyň, soumrak", "1 1/8", "Chalupa Sedlec", "Anna Geislerová"],
  [3, "8.1.2099", "7", "EXT", "DEN", "HRAD – nádvoří", "2", "Karlštejn", "Jiří Mádl"],
];
const wb = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), "Harmonogram");
XLSX.writeFile(wb, "tests/fixtures/schedule-3-days.xlsx");
console.log("wrote tests/fixtures/schedule-3-days.xlsx");
