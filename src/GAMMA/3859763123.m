Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
SpatialMap(77,77) X';
TemporalMap(31,31) Y';
TemporalMap(2,2) C;
TemporalMap(3,3) R;
TemporalMap(3,3) S;
TemporalMap(49,49) K;
Cluster(70,P);
TemporalMap(1,1) R;
TemporalMap(1,1) Y';
TemporalMap(1,1) C;
SpatialMap(1,1) X';
TemporalMap(1,1) S;
TemporalMap(1,1) K;
}
}
}