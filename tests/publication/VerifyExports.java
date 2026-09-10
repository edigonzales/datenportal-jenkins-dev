import java.sql.DriverManager;

class VerifyExports {
    public static void main(String[] args) throws Exception {
        String output = args.length > 0 ? args[0] : "/test/repo/statistikdienst/build/publication/outputs/ch.so.bevoelkerung.altersstruktur_2025.";
        try (var connection = DriverManager.getConnection("jdbc:duckdb:/test/repo/statistikdienst/build/publication/publication.duckdb");
             var sql = connection.createStatement()) {
            sql.execute("SET extension_directory='/opt/datenportal/duckdb-extensions'");
            sql.execute("LOAD excel");
            if (args.length > 1 && args[1].equals("typed")) {
                try (var rows = sql.executeQuery("SELECT * FROM read_parquet('" + output + "parquet')")) {
                    String[] expected = {"VARCHAR", "BIGINT", "DOUBLE", "BOOLEAN", "DATE", "TIMESTAMP"};
                    for (int i=0; i<expected.length; i++) {
                        String actual=rows.getMetaData().getColumnTypeName(i+1);
                        if (!actual.equals(expected[i])) throw new AssertionError("Column type: " + actual + " != " + expected[i]);
                    }
                }
                try (var rows = sql.executeQuery("SELECT code FROM read_xlsx('" + output + "xlsx', header=true, sheet='Daten')")) {
                    if (!rows.next() || !rows.getString(1).equals("0012")) throw new AssertionError("XLSX loses leading zeros");
                }
            }
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
