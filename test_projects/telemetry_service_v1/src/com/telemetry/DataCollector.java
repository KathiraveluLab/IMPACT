package com.telemetry;

public class DataCollector {
    private Database database;

    public DataCollector(Database db) {
        this.database = db;
    }

    public void collect(String info) {
        database.save(info);
    }
}
