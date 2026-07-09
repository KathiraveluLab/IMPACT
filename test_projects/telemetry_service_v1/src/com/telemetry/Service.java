package com.telemetry;

public class Service {
    private DataCollector collector;

    public void process() {
        collector.collect("metrics");
    }
}
