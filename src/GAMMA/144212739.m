Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(2,2) R;
TemporalMap(1,1) C;
SpatialMap(77,77) X';
TemporalMap(35,35) K;
TemporalMap(1,1) S;
TemporalMap(128,128) Y';
Cluster(1,P);
TemporalMap(1,1) S;
TemporalMap(1,1) K;
TemporalMap(1,1) Y';
TemporalMap(1,1) X';
SpatialMap(1,1) C;
TemporalMap(1,1) R;
}
}
}