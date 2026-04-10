Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(7,7) S;
SpatialMap(34,34) K;
TemporalMap(3,3) R;
TemporalMap(1,1) C;
TemporalMap(7,7) Y';
TemporalMap(215,215) X';
Cluster(35,P);
TemporalMap(1,1) R;
TemporalMap(1,1) K;
TemporalMap(1,1) C;
TemporalMap(1,1) S;
SpatialMap(1,1) X';
TemporalMap(1,1) Y';
}
}
}