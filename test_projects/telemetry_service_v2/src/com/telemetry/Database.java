package com.telemetry;

public class Database {
    private Service service; // Cycle introduced here!

    public void save(String data) {
        System.out.println("Saving data: " + data);
        if (service != null) {
            service.notifyUpdate();
        }
    }
}
