// Writes tests/fixtures/crew-12.xlsx: a crew list the way a Czech production office keeps it
// (title row, blank row, Czech headers, a HoD column, one odd phone, one name-only row).
import * as XLSX from "xlsx";
const rows = [
  ["Noc na Karlštejně – štáb"], [],
  ["Oddělení", "Jméno a příjmení", "Pozice", "Telefon", "HoD"],
  ["Režie", "Eva Dvořáková", "1. AD", "+420 777 111 222", "x"],
  ["Kamera", "Marek Sýkora", "DoP", "603 555 010", "x"],
  ["Kamera", "Petra Králová", "1. AC", "602 111 222", ""],
  ["Kamera", "Ondřej Bílý", "2. AC", "", ""],
  ["Osvětlovači", "Tomáš Novák", "Gaffer", "601 234 567", "ano"],
  ["Osvětlovači", "Lukáš Malý", "Best boy", "608 000 111", ""],
  ["Zvuk", "Jana Tichá", "Mistr zvuku", "604 222 333", "x"],
  ["Výprava", "Klára Veselá", "Výtvarnice", "605 987 321", "x"],
  ["Výprava", "Filip Rychlý", "Rekvizitář", "ask Klára", ""],
  ["Produkce", "Jana Bílá", "Vedoucí produkce", "606 444 555", "x"],
  ["Produkce", "Karel", "", "", ""],
  ["Doprava", "Petr Vozka", "Řidič", "777 999 000", ""],
];
const wb = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), "Štáb");
XLSX.writeFile(wb, "tests/fixtures/crew-12.xlsx");
console.log("wrote tests/fixtures/crew-12.xlsx");
