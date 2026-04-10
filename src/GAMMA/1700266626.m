Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(55,55) X';
TemporalMap(3,3) S;
TemporalMap(38,38) K;
SpatialMap(132,132) Y';
TemporalMap(3,3) R;
TemporalMap(2,2) C;
Cluster(2,P);
SpatialMap(1,1) C;
TemporalMap(1,1) R;
TemporalMap(1,1) Y';
TemporalMap(1,1) X';
TemporalMap(1,1) S;
TemporalMap(1,1) K;
}
}
}