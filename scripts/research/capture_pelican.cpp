// Standalone research generation with real activations from the output-producing execution.
#include "llama.h"
#include "ggml-backend.h"
#include "json.hpp"
#include <algorithm>
#include <cmath>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>
using json=nlohmann::ordered_json;
struct Capture { bool enabled=false; int step=-1, position=-1, token=-1; std::string text,dir,error; json samples=json::array(); };
static int layer_for(const char *name){ for(int layer:{0,31,63}) if(std::string(name)=="l_out-"+std::to_string(layer)) return layer; return -1; }
static bool capture(ggml_tensor*t,bool ask,void*raw){
 auto& c=*static_cast<Capture*>(raw);int layer=layer_for(t->name);
 if(ask)return c.enabled && layer>=0;
 if(!c.enabled || layer<0)return true;
 if(t->type!=GGML_TYPE_F32 || t->ne[0]!=5120 || t->ne[1]!=1 || t->ne[2]!=1 || t->ne[3]!=1 || !ggml_is_contiguous(t)){c.error="Unexpected activation dtype/shape/strides";return false;}
 std::vector<float> values(5120);ggml_backend_tensor_get(t,values.data(),0,values.size()*sizeof(float));
 double sum=0,squared=0;size_t nonfinite=0;float lo=values[0],hi=lo;
 for(float v:values){if(!std::isfinite(v)){++nonfinite;continue;}sum+=v;squared+=double(v)*v;lo=std::min(lo,v);hi=std::max(hi,v);}
 if(nonfinite){c.error="Nonfinite activation value";return false;}
 std::string file="step-"+std::to_string(c.step)+"-layer-"+std::to_string(layer)+".f32";
 std::ofstream out(c.dir+"/"+file,std::ios::binary);out.write(reinterpret_cast<const char*>(values.data()),values.size()*sizeof(float));if(!out){c.error="Vector write failed";return false;}
 c.samples.push_back({{"step",c.step},{"input_token_id",c.token},{"input_token_text",c.text},{"position",c.position},{"layer",layer},{"tensor",t->name},{"shape",{5120,1,1,1}},{"sample",std::vector<float>(values.begin(),values.begin()+16)},{"stats",{{"min",lo},{"max",hi},{"mean",sum/5120},{"rms",std::sqrt(squared/5120)},{"l2",std::sqrt(squared)},{"nonfinite",nonfinite}}},{"vector_file",file},{"vector_length",5120}});return true;
}
static std::string piece(const llama_vocab*v,llama_token t){std::vector<char>b(256);int n=llama_token_to_piece(v,t,b.data(),b.size(),0,true);if(n<0){b.resize(-n);n=llama_token_to_piece(v,t,b.data(),b.size(),0,true);}if(n<0)throw std::runtime_error("token conversion");return std::string(b.data(),n);}
int main(int argc,char**argv){try{
 if(argc!=4 && argc!=5)throw std::runtime_error("usage: capture MODEL RENDERED_PROMPT_FILE OUTPUT_DIR [CONFIG_JSON]");
 json config=json::object();if(argc==5){std::ifstream f(argv[4]);f>>config;}
 const int steps=config.value("decode_steps",8), context=config.value("context",1024);
 if(steps<1 || steps>4096 || context<1024 || context>65536)throw std::runtime_error("diagnostic bounds exceeded");
 std::ifstream in(argv[2]);std::string prompt((std::istreambuf_iterator<char>(in)),{});if(prompt.empty())throw std::runtime_error("empty prompt");
 Capture c;c.dir=argv[3];std::filesystem::create_directories(c.dir);ggml_backend_load_all();llama_backend_init();
 auto mp=llama_model_default_params();mp.n_gpu_layers=999;auto*m=llama_model_load_from_file(argv[1],mp);if(!m)throw std::runtime_error("model load");if(llama_model_n_embd(m)!=5120 || llama_model_n_layer(m)!=64)throw std::runtime_error("Capture supports only verified 5120-wide 64-layer models");const auto*v=llama_model_get_vocab(m);
 int n=-llama_tokenize(v,prompt.data(),prompt.size(),nullptr,0,true,true);if(n<=0||n+steps>context)throw std::runtime_error("prompt exceeds bounded diagnostic context");std::vector<llama_token>pt(n);if(llama_tokenize(v,prompt.data(),prompt.size(),pt.data(),pt.size(),true,true)!=n)throw std::runtime_error("tokenization");
 auto cp=llama_context_default_params();cp.n_ctx=context;cp.n_batch=2048;cp.n_ubatch=256;cp.n_seq_max=1;cp.n_threads=config.value("n_threads",8);cp.n_threads_batch=cp.n_threads;cp.flash_attn_type=LLAMA_FLASH_ATTN_TYPE_ENABLED;cp.cb_eval=capture;cp.cb_eval_user_data=&c;auto*ctx=llama_init_from_model(m,cp);if(!ctx)throw std::runtime_error("context init");
 if(config.contains("expected_prompt_tokens") && n!=config["expected_prompt_tokens"].get<int>())throw std::runtime_error("token count differs from recorded request");
 const auto generation_start=std::chrono::steady_clock::now();
 for(int offset=0;offset<n;offset+=256){int count=std::min(256,n-offset);if(llama_decode(ctx,llama_batch_get_one(pt.data()+offset,count)))throw std::runtime_error("prefill");}
 llama_sampler *sampler=nullptr;
 if(config.value("sampler",std::string("greedy"))=="source_sampling"){
  auto params=llama_sampler_chain_default_params();sampler=llama_sampler_chain_init(params);
  llama_sampler_chain_add(sampler,llama_sampler_init_temp(config.value("temperature",0.3f)));
  llama_sampler_chain_add(sampler,llama_sampler_init_top_k(config.value("top_k",20)));
  llama_sampler_chain_add(sampler,llama_sampler_init_top_p(config.value("top_p",0.95f),1));
  llama_sampler_chain_add(sampler,llama_sampler_init_min_p(config.value("min_p",0.0f),1));
  llama_sampler_chain_add(sampler,llama_sampler_init_dist(config.value("seed",42u)));
 }else{sampler=llama_sampler_init_greedy();}
 llama_token token=llama_sampler_sample(sampler,ctx,-1);json tokens=json::array();std::string generated;bool reached_eog=false;
 for(int step=0;step<steps;++step){if(llama_vocab_is_eog(v,token)){reached_eog=true;break;}c.enabled=true;c.step=step;c.position=n+step;c.token=token;c.text=piece(v,token);generated+=c.text;llama_sampler_accept(sampler,token);if(llama_decode(ctx,llama_batch_get_one(&token,1)))throw std::runtime_error("decode");llama_synchronize(ctx);if(!c.error.empty())throw std::runtime_error(c.error);if(c.samples.size()!=size_t((step+1)*3))throw std::runtime_error("expected3capturedlayersperstep");auto next=llama_sampler_sample(sampler,ctx,-1);tokens.push_back({{"step",step},{"input_token_id",token},{"input_token_text",c.text},{"position",c.position},{"next_token_id",next},{"next_token_text",piece(v,next)}});token=next;}
 const double generation_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-generation_start).count();
 json result={{"generation_seconds",generation_seconds},{"sampler_order",{"temperature","top_k","top_p","min_p","categorical_draw"}},{"samples",c.samples},{"tokens",tokens},{"prompt_token_ids",pt},{"prompt_token_count",n},{"generated_text",generated},{"reached_eog",reached_eog},{"decode_steps_requested",steps},{"decode_steps_captured",tokens.size()},{"passed",!tokens.empty()}};std::ofstream output(c.dir+"/capture.json");output<<result.dump(2,' ',false,json::error_handler_t::replace)<<"\n";if(!output)throw std::runtime_error("result write");
 llama_sampler_free(sampler);llama_free(ctx);llama_model_free(m);llama_backend_free();std::cout<<"Captured "<<c.samples.size()<<" actual F32 activation vectors\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
