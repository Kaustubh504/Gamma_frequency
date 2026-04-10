Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(61,61) K;
TemporalMap(3,3) C;
TemporalMap(7,7) S;
SpatialMap(4,4) X';
TemporalMap(4,4) R;
TemporalMap(105,105) Y';
Cluster(1,P);
SpatialMap(1,1) C;
TemporalMap(4,4) R;
TemporalMap(1,1) S;
TemporalMap(10,10) K;
TemporalMap(2,2) X';
TemporalMap(1,1) Y';
}
}
}