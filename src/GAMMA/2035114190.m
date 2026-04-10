Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(170,170) Y';
TemporalMap(3,3) R;
TemporalMap(177,177) X';
TemporalMap(3,3) C;
SpatialMap(49,49) K;
TemporalMap(2,2) S;
Cluster(38,P);
SpatialMap(1,1) K;
TemporalMap(1,1) R;
TemporalMap(1,1) S;
TemporalMap(1,1) X';
TemporalMap(1,1) Y';
TemporalMap(1,1) C;
}
}
}