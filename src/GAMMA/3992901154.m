Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(63,63) K;
TemporalMap(3,3) R;
TemporalMap(1,1) C;
TemporalMap(61,61) Y';
SpatialMap(80,80) X';
TemporalMap(1,1) S;
Cluster(34,P);
TemporalMap(1,1) X';
TemporalMap(1,1) S;
TemporalMap(1,1) C;
TemporalMap(1,1) Y';
TemporalMap(1,1) R;
SpatialMap(1,1) K;
}
}
}