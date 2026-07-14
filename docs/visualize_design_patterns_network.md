# Visualizing the 1,739-Class Dependency Network of the Java Design Patterns Repository

This analysis outlines the engineering and rendering approaches utilized by IMPACT to visualize and perform intent evaluation on massive code bases, referencing `iluwatar/java-design-patterns`.

---

## 1. The Challenge of Massive Dependency Networks
The target project `iluwatar/java-design-patterns` contains:
* **Total Classes**: 1,739
* **Total Dependencies (Edges)**: ~5,200
* **Modularity structure**: Over 80 design pattern subfolders (e.g. factory, singleton, builder, visitor).

In a standard force-directed layout:
* High node count causes rendering lag (low frame rates due to $O(N^2)$ repelling force computations).
* The layout resembles a "hairball", making it impossible for developers to detect dependency cycles or coupling leaks.

---

## 2. Rendering Optimization Strategies

### A. Modular/Hierarchy Clustering
Instead of laying out all 1,739 classes at the same level, IMPACT groups nodes by their Java package/directory namespaces:
1. **Design Pattern Clusters**: Each design pattern is represented as a single cluster node.
2. **Inner/Outer layouts**:
   * **Force layout (global)**: Nodes representing clusters repel each other.
   * **Circular layout (local) (Task 18a)**: Inside each cluster, classes are positioned in a circular ring to clearly display internal dependencies and highlight cyclic calls.

```mermaid
graph TD
    subgraph Cluster A: Singleton
        S1[SingletonClass] --> S2[DbConn]
    end
    subgraph Cluster B: Factory
        F1[FactoryClass] --> F2[ProductClass]
    end
    Cluster B -->|calls| Cluster A
```

### B. Canvas Rendering and Physics Decoupling
To maintain a high frame rate (>60 FPS) in the web browser:
1. **Offscreen Canvas Canvas Buffering**: Static nodes are drawn once on an offscreen buffer, with only active cycle lines and hovered elements drawn on the active frame.
2. **Physics Bypassing (Task 18a)**: In circular layout mode, physics force computations are completely disabled after nodes are positioned, removing the $O(N^2)$ force calculation overhead.
3. **Lazy Lod (Level of Detail)**: Class text labels are only rendered when the zoom level is greater than 1.5, saving substantial text drawing overhead.
