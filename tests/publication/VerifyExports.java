import java.sql.DriverManager;

class VerifyExports {
    public static void main(String[] args) throws Exception {
        String output = "/test/repo/statistikdienst/build/publication/outputs/ch.so.bevoelkerung.altersstruktur_2025.";
        try (var connection = DriverManager.getConnection("jdbc:duckdb:/test/repo/statistikdienst/build/publication/publication.duckdb");
             var sql = connection.createStatement()) {
            sql.execute("SET extension_directory='/opt/datenportal/duckdb-extensions'");
            sql.execute("LOAD excel");
            for (String table : new String[]{"read_parquet('" + output + "parquet')",
                    "read_xlsx('" + output + "xlsx', header=true, sheet='Daten')"}) {
                String query = "SELECT count(*) FROM ((SELECT * FROM data.records EXCEPT ALL SELECT * FROM "
                        + table + ") UNION ALL (SELECT * FROM " + table + " EXCEPT ALL SELECT * FROM data.records))";
                try (var differences = sql.executeQuery(query)) {
                    differences.next();
                    if (differences.getInt(1) != 0) throw new AssertionError("Export changes data: " + table);
                }
            }
        }
        System.out.println("XLSX and Parquet preserve every input value and row.");
    }
}
