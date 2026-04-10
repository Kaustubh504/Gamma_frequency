Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(5,5) R;
TemporalMap(11,11) Y';
TemporalMap(2,2) S;
SpatialMap(31,31) K;
TemporalMap(2,2) C;
TemporalMap(197,197) X';
Cluster(6,P);
TemporalMap(1,1) S;
SpatialMap(1,1) Y';
TemporalMap(1,1) R;
TemporalMap(1,1) K;
TemporalMap(1,1) X';
TemporalMap(1,1) C;
}
}
}