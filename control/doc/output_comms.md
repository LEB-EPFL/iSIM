```mermaid
sequenceDiagram
    participant GUI
    participant Relay
    participant Brokers
    participant Writer
    participant Viewer
    participant PositionHistory

    GUI->>Relay: setting up Acquisition
    Relay->>Brokers: setting up Acquisition
```