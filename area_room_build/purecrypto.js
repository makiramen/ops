/* Minimal SHA-256, HMAC, PBKDF2 and AES-256-CTR. Used when the viewer has no WebCrypto. */
var PC=(function(){
var K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
var IV=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
var W=new Uint32Array(64);
function block(H,w16){
  for(var i=0;i<16;i++)W[i]=w16[i];
  for(i=16;i<64;i++){var x=W[i-15],y=W[i-2];
    var s0=((x>>>7)|(x<<25))^((x>>>18)|(x<<14))^(x>>>3),s1=((y>>>17)|(y<<15))^((y>>>19)|(y<<13))^(y>>>10);
    W[i]=(W[i-16]+s0+W[i-7]+s1)|0}
  var a=H[0],b=H[1],c=H[2],d=H[3],e=H[4],f=H[5],g=H[6],h=H[7];
  for(i=0;i<64;i++){
    var S1=((e>>>6)|(e<<26))^((e>>>11)|(e<<21))^((e>>>25)|(e<<7)),ch=(e&f)^(~e&g),t1=(h+S1+ch+K[i]+W[i])|0;
    var S0=((a>>>2)|(a<<30))^((a>>>13)|(a<<19))^((a>>>22)|(a<<10)),mj=(a&b)^(a&c)^(b&c),t2=(S0+mj)|0;
    h=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0}
  H[0]=(H[0]+a)|0;H[1]=(H[1]+b)|0;H[2]=(H[2]+c)|0;H[3]=(H[3]+d)|0;H[4]=(H[4]+e)|0;H[5]=(H[5]+f)|0;H[6]=(H[6]+g)|0;H[7]=(H[7]+h)|0;
}
function sha256(msg,initH,prefixLen){
  var H=new Int32Array(initH||IV),pl=prefixLen||0,len=msg.length,tot=len+pl;
  var nb=Math.ceil((len+9)/64),buf=new Uint8Array(nb*64);buf.set(msg);buf[len]=0x80;
  var bits=tot*8;buf[nb*64-4]=(bits>>>24)&255;buf[nb*64-3]=(bits>>>16)&255;buf[nb*64-2]=(bits>>>8)&255;buf[nb*64-1]=bits&255;
  buf[nb*64-5]=Math.floor(tot/0x20000000)&255;
  var w=new Uint32Array(16);
  for(var bi=0;bi<nb;bi++){for(var j=0;j<16;j++){var o=bi*64+j*4;w[j]=(buf[o]<<24)|(buf[o+1]<<16)|(buf[o+2]<<8)|buf[o+3]}block(H,w)}
  var out=new Uint8Array(32);for(var k=0;k<8;k++){out[k*4]=H[k]>>>24;out[k*4+1]=H[k]>>>16;out[k*4+2]=H[k]>>>8;out[k*4+3]=H[k]}
  return out;
}
function padState(key,byte){var k=new Uint8Array(64);if(key.length>64)key=sha256(key);k.set(key);
  for(var i=0;i<64;i++)k[i]^=byte;var H=new Int32Array(IV),w=new Uint32Array(16);
  for(var j=0;j<16;j++)w[j]=(k[j*4]<<24)|(k[j*4+1]<<16)|(k[j*4+2]<<8)|k[j*4+3];block(H,w);return H}
function hmacWith(ist,ost,msg){return sha256(sha256(msg,ist,64),ost,64)}
function hmac(key,msg){return hmacWith(padState(key,0x36),padState(key,0x5c),msg)}
function pbkdf2(pw,salt,iter,dkLen){
  var ist=padState(pw,0x36),ost=padState(pw,0x5c),out=new Uint8Array(dkLen),blocks=Math.ceil(dkLen/32);
  for(var b=1;b<=blocks;b++){
    var s=new Uint8Array(salt.length+4);s.set(salt);s[salt.length]=b>>>24;s[salt.length+1]=b>>>16;s[salt.length+2]=b>>>8;s[salt.length+3]=b;
    var u=hmacWith(ist,ost,s),t=u.slice();
    for(var i=1;i<iter;i++){u=hmacWith(ist,ost,u);for(var j=0;j<32;j++)t[j]^=u[j]}
    out.set(t.subarray(0,Math.min(32,dkLen-(b-1)*32)),(b-1)*32)}
  return out;
}
/* AES-256 */
var SB=new Uint8Array(256),XT=function(a){return ((a<<1)^((a&0x80)?0x1b:0))&255};
(function(){var p=1,q=1;do{p=p^((p<<1)&255)^((p&0x80)?0x1b:0);q^=q<<1;q^=q<<2;q^=q<<4;q&=255;if(q&0x80)q^=0x09;
  var x=q^((q<<1|q>>>7)&255)^((q<<2|q>>>6)&255)^((q<<3|q>>>5)&255)^((q<<4|q>>>4)&255);SB[p]=(x^0x63)&255}while(p!==1);SB[0]=0x63})();
function expand(key){var w=new Uint8Array(240);w.set(key);var rc=1;
  for(var i=32;i<240;i+=4){var t=[w[i-4],w[i-3],w[i-2],w[i-1]];
    if(i%32===0){t=[SB[t[1]]^rc,SB[t[2]],SB[t[3]],SB[t[0]]];rc=XT(rc)}else if(i%32===16){t=[SB[t[0]],SB[t[1]],SB[t[2]],SB[t[3]]]}
    for(var j=0;j<4;j++)w[i+j]=w[i-32+j]^t[j]}return w}
function encBlock(w,inp){var s=new Uint8Array(16),i,r,c;for(i=0;i<16;i++)s[i]=inp[i]^w[i];
  for(r=1;r<=14;r++){for(i=0;i<16;i++)s[i]=SB[s[i]];
    var t=s.slice();for(c=0;c<4;c++)for(i=0;i<4;i++)s[c*4+i]=t[((c+i)%4)*4+i];
    if(r<14)for(c=0;c<4;c++){var a0=s[c*4],a1=s[c*4+1],a2=s[c*4+2],a3=s[c*4+3],x=a0^a1^a2^a3;
      s[c*4]^=x^XT(a0^a1);s[c*4+1]^=x^XT(a1^a2);s[c*4+2]^=x^XT(a2^a3);s[c*4+3]^=x^XT(a3^a0)}
    for(i=0;i<16;i++)s[i]^=w[r*16+i]}return s}
function ctr(key,iv,data){var w=expand(key),out=new Uint8Array(data.length),cb=iv.slice();
  for(var o=0;o<data.length;o+=16){var ks=encBlock(w,cb);for(var i=0;i<16&&o+i<data.length;i++)out[o+i]=data[o+i]^ks[i];
    for(var k=15;k>=0;k--){cb[k]=(cb[k]+1)&255;if(cb[k])break}}return out}
return {sha256:sha256,hmac:hmac,pbkdf2:pbkdf2,ctr:ctr};
})();
