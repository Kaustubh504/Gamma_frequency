Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(1,1) S;
TemporalMap(129,129) X';
TemporalMap(36,36) K;
TemporalMap(2,2) R;
SpatialMap(1,1) C;
TemporalMap(206,206) Y';
Cluster(1,P);
TemporalMap(1,1) K;
TemporalMap(1,1) Y';
TemporalMap(1,1) R;
TemporalMap(1,1) S;
TemporalMap(1,1) X';
SpatialMap(1,1) C;
}
}
}