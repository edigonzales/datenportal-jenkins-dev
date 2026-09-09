import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.List;

/** Verifies the image's native extensions and actual exported values via JDBC. */
class VerifyDuckDb {
    public static void main(String[] args) throws Exception {
        Path extensionDirectory = Path.of(System.getenv("DUCKDB_EXTENSION_DIRECTORY")).toRealPath();
        try (var connection = DriverManager.getConnection("jdbc:duckdb:");
             var statement = connection.createStatement()) {
            statement.execute("SET extension_directory = " + literal(extensionDirectory.toString()));
            statement.execute("SET autoinstall_known_extensions = false");
            statement.execute("SET autoload_known_extensions = false");
            for (String extension : List.of("postgres", "spatial", "excel")) {
                statement.execute("LOAD " + extension);
                // DuckDB stores the postgres alias as postgres_scanner.
                String name = extension.equals("postgres") ? "postgres_scanner" : extension;
                try (ResultSet result = statement.executeQuery(
                        "SELECT loaded, installed, install_path FROM duckdb_extensions() WHERE extension_name = " + literal(name))) {
                    require(result.next(), "Missing extension: " + extension);
                    require(result.getBoolean(1) && result.getBoolean(2), "Extension not installed/loaded: " + extension);
                    Path installed = Path.of(result.getString(3)).toRealPath();
                    require(installed.startsWith(extensionDirectory), "Extension loaded outside image directory: " + installed);
                    require(!Files.isWritable(installed), "Extension writable by Jenkins: " + installed);
                    System.out.println("Loaded " + extension + " from " + installed);
                }
            }
            try (ResultSet result = statement.executeQuery("SELECT ST_AsText(ST_Point(7, 47))")) {
                require(result.next() && result.getString(1).equals("POINT (7 47)"), "Spatial function failed");
            }
            if (args.length == 2) {
                verifyRows(statement, "read_parquet(" + literal(args[0]) + ")");
                verifyRows(statement, "read_xlsx(" + literal(args[1]) + ", header = true, sheet = 'Records')");
                System.out.println("Parquet and XLSX columns and all values verified.");
            }
        }
    }

    private static void verifyRows(Statement statement, String source) throws Exception {
        try (ResultSet result = statement.executeQuery("SELECT * FROM " + source + " ORDER BY id")) {
            var metadata = result.getMetaData();
            require(metadata.getColumnCount() == 3, "Unexpected column count");
            for (int i = 0; i < 3; i++) {
                require(metadata.getColumnLabel(i + 1).equals(List.of("id", "name", "doubled_amount").get(i)), "Unexpected column name");
            }
            String[] names = {"AARAU", "OLTEN", "ZÜRICH"};
            int[] amounts = {14, 22, 6};
            for (int i = 0; i < names.length; i++) {
                require(result.next(), "Missing row");
                require(result.getDouble(1) == i + 1 && !result.wasNull(), "Wrong id");
                require(names[i].equals(result.getString(2)), "Wrong text value");
                require(result.getDouble(3) == amounts[i] && !result.wasNull(), "Wrong numeric value");
            }
            require(!result.next(), "Unexpected extra row");
        }
    }

    private static String literal(String value) {
        return "'" + value.replace("'", "''") + "'";
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new IllegalStateException(message);
        }
    }
}
