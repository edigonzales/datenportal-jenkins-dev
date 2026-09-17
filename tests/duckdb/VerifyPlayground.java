import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.file.*;
import java.sql.*;
import java.util.*;

/** Exercises the canonical publisher SQL and resulting remote views, with loopback HTTP only. */
class VerifyPlayground {
    static Path work;
    static String generator;
    static String base;

    public static void main(String[] args) throws Exception {
        work = Files.createTempDirectory("playground-contract-");
        generator = Files.readString(Path.of(args[0]));
        Path parquet = work.resolve("fixture.parquet");
        try (var connection = open(); var sql = connection.createStatement()) {
            sql.execute("COPY (SELECT 42 AS id, 'Solothurn' AS name) TO " + literal(parquet.toString()) + " (FORMAT PARQUET)");
        }
        byte[] data = Files.readAllBytes(parquet);
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            if (exchange.getRequestURI().getPath().contains("missing")) {
                exchange.sendResponseHeaders(404, -1); exchange.close(); return;
            }
            exchange.getResponseHeaders().set("Accept-Ranges", "bytes");
            if (exchange.getRequestMethod().equals("HEAD")) {
                exchange.getResponseHeaders().set("Content-Length", Integer.toString(data.length));
                exchange.sendResponseHeaders(200, -1);
            } else {
                String range = exchange.getRequestHeaders().getFirst("Range");
                int start = 0, end = data.length - 1;
                if (range != null) {
                    String[] bounds = range.substring(6).split("-", -1);
                    start = Integer.parseInt(bounds[0]);
                    if (!bounds[1].isEmpty()) end = Math.min(end, Integer.parseInt(bounds[1]));
                    exchange.getResponseHeaders().set("Content-Range", "bytes " + start + "-" + end + "/" + data.length);
                }
                exchange.sendResponseHeaders(range == null ? 200 : 206, end-start+1);
                exchange.getResponseBody().write(data, start, end-start+1);
            }
            exchange.close();
        });
        server.start();
        base = "http://127.0.0.1:" + server.getAddress().getPort() + "/";
        try {
            verify("visible", "INSERT INTO candidate.distribution VALUES ('parquet'," + literal(base+"normal.data.parquet?note=O'Brien;ok") + ",1),"
                    + "('parquet'," + literal(base+"old.parquet") + ",2),('parquet'," + literal(base+"current.parquet") + ",3),"
                    + "('parquet'," + literal(base+"hidden.parquet") + ",4),('parquet'," + literal(base+"hidden_series.parquet") + ",5);", 3, null);
            verify("empty", "", 0, null);
            verify("collision", distributions("a.b.parquet", "A_B.parquet"), 0, "Duplicate playground");
            verify("invalid-name", distributions("invalid-name.parquet"), 0, "Invalid public");
            verify("invalid-url", "INSERT INTO candidate.distribution VALUES ('parquet','file:///tmp/data.parquet',1)", 0, "Invalid public");
            verify("missing", distributions("missing.parquet"), 0, "404");
            System.out.println("Playground SQL: selection, historical issues, empty catalog, escaping, collisions and HTTP failures passed.");
        } finally {
            server.stop(0);
            try (var paths = Files.walk(work)) {
                for (var path : paths.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(path);
            }
        }
    }

    static Connection open() throws Exception {
        var connection = DriverManager.getConnection("jdbc:duckdb:");
        try (var sql = connection.createStatement()) {
            String directory = System.getenv("DUCKDB_EXTENSION_DIRECTORY");
            if (directory != null) sql.execute("SET extension_directory=" + literal(directory));
            sql.execute("SET autoinstall_known_extensions=false");
        }
        return connection;
    }

    static void verify(String name, String inserts, int expected, String failure) throws Exception {
        Path generated = work.resolve(name+".sql");
        try {
            try (var connection = open(); var sql = connection.createStatement()) {
                sql.execute("CREATE SCHEMA work; CREATE SCHEMA candidate;"
                    + "CREATE TABLE candidate.dataset(t_id BIGINT,publicationstatus VARCHAR,datasetseries_issues BIGINT);"
                    + "CREATE TABLE candidate.datasetseries(t_id BIGINT,publicationstatus VARCHAR);"
                    + "CREATE TABLE candidate.distribution(aformat VARCHAR,downloadurl VARCHAR,dataset_distributions BIGINT);"
                    + "INSERT INTO candidate.datasetseries VALUES (10,'published'),(11,'in_review');"
                    + "INSERT INTO candidate.dataset VALUES (1,'published',NULL),(2,'published',10),(3,'published',10),(4,'archived',NULL),(5,'published',11);");
                if (!inserts.isEmpty()) sql.execute(inserts);
                sql.execute(generator.replace("${playground_sql}", literal(generated.toString())));
            }
            try (var connection = open(); var sql = connection.createStatement()) {
                var reader = new ch.so.agi.gretl.util.SqlReader();
                try {
                    String statement = reader.readSqlStmt(generated.toFile(), Map.of());
                    while (statement != null) {
                        sql.execute(statement);
                        statement = reader.nextSqlStmt();
                    }
                } finally { reader.close(); }
                var views = sql.executeQuery("SELECT view_name FROM duckdb_views() WHERE schema_name='opendata' ORDER BY view_name");
                var names = new ArrayList<String>();
                while (views.next()) names.add(views.getString(1));
                if (names.size() != expected) throw new AssertionError(names);
                for (String view : names) {
                    var rows = sql.executeQuery("SELECT id FROM opendata.\""+view+"\"");
                    if (!rows.next() || rows.getInt(1) != 42) throw new AssertionError(view);
                }
            }
            if (failure != null) throw new AssertionError(name+" should fail");
        } catch (SQLException error) {
            if (failure == null || !error.getMessage().contains(failure)) throw error;
        }
    }

    static String distributions(String... names) {
        return "INSERT INTO candidate.distribution VALUES " + String.join(",", Arrays.stream(names)
                .map(name -> "('parquet',"+literal(base+name)+",1)").toList());
    }
    static String literal(String value) { return "'" + value.replace("'", "''") + "'"; }
}
