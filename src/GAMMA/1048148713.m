Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(2,2) S;
TemporalMap(2,2) C;
TemporalMap(22,22) K;
TemporalMap(2,2) R;
TemporalMap(38,38) X';
SpatialMap(44,44) Y';
Cluster(10,P);
TemporalMap(1,1) Y';
TemporalMap(1,1) X';
SpatialMap(1,1) K;
TemporalMap(1,1) S;
TemporalMap(1,1) R;
TemporalMap(1,1) C;
}
}
}