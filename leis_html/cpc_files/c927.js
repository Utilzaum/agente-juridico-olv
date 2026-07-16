carregaC927();
function carregaC927(){
	
	var pathArray = window.location.pathname.split('/');
	var ultimaPosicao = pathArray.length - 1
	var atoHTML = pathArray[ultimaPosicao];

	atoHTML = atoHTML.toUpperCase();
	var atoArray = atoHTML.split('.');
	var ato = atoArray[0];

	ato = ato.replace('_C927', '');
	var url = obterURLCorpus(ato);
	var tagsC927 = document.getElementsByClassName("c927");
	
	for (var i = 0; i < tagsC927.length; i++) {
		//Obtem o artigo que faz referencia ao c927
		var artigo = tagsC927[i].getAttribute("name");
		artigo = artigo.replace(/[^\d]+/g,'');
		//Monta o endereço do link para o c927
		urlC927 = url+"#art-"+artigo;
		//Atribui o endereço do link para o c927 
		tagsC927[i].setAttribute("href", urlC927);
		tagsC927[i].setAttribute("target", "_blank");
		tagsC927[i].setAttribute("alt", "Visualizar Jurisprudencia Consolidada do Artigo n. "+ artigo +" - Corpus927");
		tagsC927[i].setAttribute("title", "Visualizar Jurisprudencia Consolidada do Artigo n. "+ artigo +" - Corpus927");
		//Mostra o conteúdo da tag
		tagsC927[i].innerHTML = '<i class="fas fa-gavel"></i>';
	}
}


function obterURLCorpus(ato){
	
	var urlCorpus = "";
	
	switch (ato) {
	  case 'L10406':
		    urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cc-02';
		    break;
	  case 'L5869':
			urlCorpus = 'http://corpus927.enfam.jus.br';
		    break;
	  case 'L13105':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cpc-15';
		    break;
	  case 'DEL2848':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cp-40';
		    break;
	  case 'DEL3689':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cpp-41';
		    break;
	  case 'L5172':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/ctn-66';
		    break;
	  case 'DEL5452':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/CLT-43';
		    break;
	  case 'L8078':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cdc-90';
		    break;
	  case 'L9503':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/ctb-97';
		    break;
	  case 'L4737':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cel-65';
		    break;
	  case 'L12651':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cflo-12';
		    break;
	  case 'D24643':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/ca-34';
		    break;
	  case 'DEL0227':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/del-227-1967';
		    break;
	  case 'DEL1001':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cpm-69';
		    break;
	  case 'DEL1002':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/CPPM-69';
		    break;
	  case 'L7565':
 			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/cba-86';
		    break;
	  case 'LIM556':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/ccm-50';
		    break;
	  case 'L4117':
			urlCorpus = 'http://corpus927.enfam.jus.br/legislacao/lei-4117-1962';
		    break;	
	  default:
			urlCorpus = 'http://corpus927.enfam.jus.br';
	}

	return 	urlCorpus;
	
}